import os
import re
import json
import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

MODEL = "openai/gpt-oss-120b"

st.set_page_config(page_title="Interview Coach", page_icon="🎯", layout="centered")


# ----------------------------------------------------------------------
# setup
# ----------------------------------------------------------------------
def get_key():
    """Key comes from .env locally, or Streamlit secrets when deployed."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        try:
            key = st.secrets["GROQ_API_KEY"]
        except Exception:
            key = None
    return key


API_KEY = get_key()
if not API_KEY:
    st.error("No GROQ_API_KEY found. Add it to .env locally, or to Secrets on Streamlit Cloud.")
    st.stop()

client = Groq(api_key=API_KEY)


def load_prompt(name):
    with open(name, encoding="utf-8") as f:
        return f.read()


QUESTION_PROMPT = load_prompt("prompt.txt")
SCORING_PROMPT = load_prompt("prompt_scoring.txt")


# session state
for key, default in [
    ("questions", []),      # list of question strings
    ("raw_output", ""),     # full markdown from the generator
    ("jd", ""),
    ("history", []),        # list of attempt dicts
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ----------------------------------------------------------------------
# model calls
# ----------------------------------------------------------------------
def call_model(prompt, temperature=0.4):
    r = client.chat.completions.create(
        model=MODEL,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.choices[0].message.content


def extract_questions(markdown_text):
    """Pull the bolded numbered questions out of the generator's markdown.

    The question prompt formats each as:  **1. the question**
    """
    found = re.findall(r"\*\*\s*\d+\.\s*(.+?)\*\*", markdown_text, flags=re.DOTALL)
    return [re.sub(r"\s+", " ", q).strip() for q in found]


def parse_json(text):
    """LLMs sometimes wrap JSON in prose or a code fence. Take the outermost braces."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


DIMENSIONS = ["specificity", "structure", "evidence", "relevance"]


def score_answer(question, answer):
    prompt = (
        SCORING_PROMPT
        + "\n\nINTERVIEW QUESTION:\n" + question
        + "\n\nCANDIDATE ANSWER:\n" + answer
    )
    raw = call_model(prompt, temperature=0.2)
    data = parse_json(raw)
    if not data:
        return None, raw

    # defensive: make sure every dimension is present and in range
    for d in DIMENSIONS:
        block = data.get(d) or {}
        try:
            s = int(block.get("score", 0))
        except (TypeError, ValueError):
            s = 0
        data[d] = {"score": max(1, min(5, s)), "reason": str(block.get("reason", "")).strip()}
    return data, raw


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------
st.title("Interview Coach")
st.caption("Paste a job posting, get questions grounded in it, then practise answering and track your scores.")

tab_q, tab_p, tab_h = st.tabs(["1 · Questions", "2 · Practise", "3 · Progress"])


# ---------------- tab 1: questions ----------------
with tab_q:
    jd = st.text_area(
        "Job description",
        value=st.session_state["jd"],
        height=240,
        placeholder="Paste the full job posting here...",
    )

    if st.button("Generate questions", type="primary"):
        if not jd.strip():
            st.warning("Paste a job description first.")
        else:
            with st.spinner("Reading the posting..."):
                out = call_model(QUESTION_PROMPT + jd)
            st.session_state["jd"] = jd
            st.session_state["raw_output"] = out
            st.session_state["questions"] = extract_questions(out)

    if st.session_state["raw_output"]:
        st.markdown(st.session_state["raw_output"])
        n = len(st.session_state["questions"])
        if n:
            st.success(f"{n} questions ready. Go to the Practise tab to answer one.")
        else:
            st.info("Questions generated, but none could be parsed for practice. Check the output format.")


# ---------------- tab 2: practise ----------------
with tab_p:
    if not st.session_state["questions"]:
        st.info("Generate questions first on the Questions tab.")
    else:
        choice = st.selectbox(
            "Which question do you want to practise?",
            st.session_state["questions"],
            index=0,
        )

        answer = st.text_area(
            "Your answer",
            height=220,
            placeholder="Answer out loud first, then type roughly what you said. Rough is fine - that is the point.",
            key="answer_box",
        )

        words = len(answer.split())
        st.caption(f"{words} words")

        if st.button("Score my answer", type="primary"):
            if words < 10:
                st.warning("Write a bit more - at least a couple of sentences.")
            else:
                with st.spinner("Scoring..."):
                    data, raw = score_answer(choice, answer)

                if not data:
                    st.error("Could not read the scoring response. Try again.")
                    with st.expander("Raw model output"):
                        st.code(raw)
                else:
                    scores = [data[d]["score"] for d in DIMENSIONS]
                    overall = round(sum(scores) / len(scores), 1)

                    st.subheader(f"Overall {overall} / 5")

                    cols = st.columns(4)
                    for col, d in zip(cols, DIMENSIONS):
                        col.metric(d.capitalize(), f"{data[d]['score']}/5")

                    for d in DIMENSIONS:
                        st.markdown(f"**{d.capitalize()} — {data[d]['score']}/5**  \n{data[d]['reason']}")

                    if data.get("strongest"):
                        st.success("Strongest: " + data["strongest"])
                    if data.get("weakest"):
                        st.warning("Weakest: " + data["weakest"])
                    if data.get("rewrite"):
                        st.info("Try saying: " + data["rewrite"])

                    st.session_state["history"].append({
                        "time": datetime.datetime.now().strftime("%H:%M:%S"),
                        "question": choice[:70] + ("..." if len(choice) > 70 else ""),
                        "words": words,
                        **{d: data[d]["score"] for d in DIMENSIONS},
                        "overall": overall,
                    })


# ---------------- tab 3: progress ----------------
with tab_h:
    hist = st.session_state["history"]

    if not hist:
        st.info("No attempts yet. Score an answer on the Practise tab and it will appear here.")
    else:
        df = pd.DataFrame(hist)
        df.insert(0, "attempt", range(1, len(df) + 1))

        c1, c2, c3 = st.columns(3)
        c1.metric("Attempts", len(df))
        c2.metric("Average", f"{df['overall'].mean():.1f}/5")
        if len(df) > 1:
            delta = df["overall"].iloc[-1] - df["overall"].iloc[0]
            c3.metric("Change", f"{delta:+.1f}")
        else:
            c3.metric("Change", "—")

        st.subheader("Scores by attempt")
        st.line_chart(df.set_index("attempt")[DIMENSIONS + ["overall"]])

        st.subheader("Weakest dimension so far")
        means = df[DIMENSIONS].mean().sort_values()
        st.write(
            f"**{means.index[0].capitalize()}** at {means.iloc[0]:.1f}/5 average — "
            "this is what to work on next."
        )
        st.bar_chart(means)

        st.subheader("All attempts")
        st.dataframe(df, width="stretch", hide_index=True)

        st.download_button(
            "Download my practice history (CSV)",
            df.to_csv(index=False).encode("utf-8"),
            file_name="interview_practice_history.csv",
            mime="text/csv",
        )
        st.caption(
            "History is kept for this browser session only. Download it if you want to keep it - "
            "accounts and saved history are not in v0.1."
        )
