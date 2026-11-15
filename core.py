"""Shared setup: the API client, the prompts, input routing, and the checks.

Split out of app.py so both pages can import it without either page owning
things the other needs.
"""

import os
import re
import json

import streamlit as st
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

MODEL = "openai/gpt-oss-120b"
DIMENSIONS = ["specificity", "structure", "evidence", "relevance"]


# ----------------------------------------------------------------------
# styling
# ----------------------------------------------------------------------
def inject_css():
    # Deliberately uncached. st.cache_data would hold the first read for the
    # life of the process, so edits to style.css would not appear until the
    # server restarted.
    here = os.path.dirname(os.path.abspath(__file__))
    # fonts.css first: it carries the embedded @font-face rules, which must
    # be defined before anything references the families.
    sheets = []
    for name in ("fonts.css", "style.css"):
        with open(os.path.join(here, name), encoding="utf-8") as f:
            sheets.append(f.read())
    st.markdown("<style>" + "\n".join(sheets) + "</style>", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# api
# ----------------------------------------------------------------------
def get_key():
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        try:
            key = st.secrets["GROQ_API_KEY"]
        except Exception:
            key = None
    return key


def get_client():
    key = get_key()
    if not key:
        st.error("No GROQ_API_KEY found. Add it to .env locally, or to Secrets on Streamlit Cloud.")
        st.stop()
    return Groq(api_key=key)


def _prompt(name):
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, name), encoding="utf-8") as f:
        return f.read()


def prompts():
    return _prompt("prompt.txt"), _prompt("prompt_role.txt"), _prompt("prompt_scoring.txt")


def call_model(prompt, temperature=0.4):
    r = get_client().chat.completions.create(
        model=MODEL, temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.choices[0].message.content


# ----------------------------------------------------------------------
# input routing
# ----------------------------------------------------------------------
POSTING_SIGNALS = (
    "responsibilit", "qualificat", "requirement", "you will", "we are looking",
    "experience with", "preferred", "nice to have", "about the role",
    "what you'll", "what you will", "years of", "degree in", "proficien",
    "familiar with", "ability to", "the ideal candidate", "benefits",
)


def classify_input(text):
    """Posting or bare role title? A rule, not a model call - instant, free,
    and the same answer every time, which matters because the user is told
    which mode fired and should be able to predict it."""
    stripped = text.strip()
    words = len(stripped.split())
    lowered = stripped.lower()
    signals = sum(1 for s in POSTING_SIGNALS if s in lowered)
    lines = [ln for ln in stripped.splitlines() if ln.strip()]

    if words < 25 and signals == 0:
        return "role"
    if words < 60 and signals < 2 and len(lines) < 4:
        return "role"
    return "posting"


# ----------------------------------------------------------------------
# grounding verification
# ----------------------------------------------------------------------
# Each question claims to quote the posting. That is a claim the reader
# cannot reasonably check six times by hand, so the app checks it.
# Normalization covers formatting only - case, whitespace, smart quotes,
# dashes - never wording, because "verbatim" is the point of the claim.

_SMART = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", " ": " ",
}


def normalize(text):
    for a, b in _SMART.items():
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip().lower()


def cite_found(phrase, source_text):
    return bool(phrase) and normalize(phrase) in normalize(source_text)


# ----------------------------------------------------------------------
# parsing model output
# ----------------------------------------------------------------------
def extract_questions(markdown_text):
    found = re.findall(r"\*\*\s*\d+\.\s*(.+?)\*\*", markdown_text, flags=re.DOTALL)
    return [re.sub(r"\s+", " ", q).strip() for q in found]


def parse_json(text):
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def score_answer(question, answer):
    _, _, scoring = prompts()
    raw = call_model(
        scoring + "\n\nINTERVIEW QUESTION:\n" + question
        + "\n\nCANDIDATE ANSWER:\n" + answer,
        temperature=0.2,
    )
    data = parse_json(raw)
    if not data:
        return None, raw
    for d in DIMENSIONS:
        block = data.get(d) or {}
        try:
            s = int(block.get("score", 0))
        except (TypeError, ValueError):
            s = 0
        data[d] = {"score": max(1, min(5, s)), "reason": str(block.get("reason", "")).strip()}
    return data, raw


def short(text, n=60):
    return text[:n] + ("..." if len(text) > n else "")


def init_state():
    for key, default in [
        ("questions", []), ("raw_output", ""), ("jd", ""), ("mode", ""),
        ("profile", ""),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default


EXAMPLE_POSTING = """Data Analyst, Customer Insights
Boston, MA (hybrid, 3 days on site)

About the role
Our Customer Insights team turns raw product and billing data into decisions
the commercial organization can act on. You will own reporting for two business
lines and act as the analytical partner to their leads.

Key responsibilities
- Build and maintain dashboards in Tableau covering retention, churn and
  expansion revenue
- Write and optimize SQL against a Snowflake warehouse, including models that
  other analysts depend on
- Partner with non-technical stakeholders to turn vague questions into
  measurable analyses, and present findings to directors
- Investigate data quality issues and drive them to resolution with the data
  engineering team

Qualifications
- 2+ years of experience with SQL in a production analytics environment
- Demonstrated ability to communicate findings clearly to a non-technical
  audience
- Experience with Python for analysis is preferred
- Degree in a quantitative field, or equivalent practical experience
"""
