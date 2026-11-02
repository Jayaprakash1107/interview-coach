import os
import re
import json
import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

import storage

load_dotenv()
storage.init_db()

MODEL = "openai/gpt-oss-120b"
DIMENSIONS = ["specificity", "structure", "evidence", "relevance"]

st.set_page_config(page_title="Interview Coach", page_icon="🎯", layout="centered")


# ----------------------------------------------------------------------
# setup
# ----------------------------------------------------------------------
def get_key():
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


GROUNDED_PROMPT = load_prompt("prompt.txt")
ROLE_PROMPT = load_prompt("prompt_role.txt")
SCORING_PROMPT = load_prompt("prompt_scoring.txt")

for key, default in [
    ("questions", []), ("raw_output", ""), ("jd", ""), ("mode", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default


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
# model calls
# ----------------------------------------------------------------------
def call_model(prompt, temperature=0.4):
    r = client.chat.completions.create(
        model=MODEL, temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.choices[0].message.content


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
    prompt = (SCORING_PROMPT
              + "\n\nINTERVIEW QUESTION:\n" + question
              + "\n\nCANDIDATE ANSWER:\n" + answer)
    raw = call_model(prompt, temperature=0.2)
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


# ----------------------------------------------------------------------
# sidebar: who is practising
# ----------------------------------------------------------------------
with st.sidebar:
    st.subheader("Practice profile")
    st.caption("Your attempts are saved under this name so you can see progress across sessions.")

    existing = [p for p, _ in storage.list_profiles()]
    if existing:
        picked = st.selectbox("Existing", ["(new)"] + existing, index=0)
    else:
        picked = "(new)"

    if picked == "(new)":
        profile = st.text_input("Name or nickname", value="", placeholder="e.g. jay")
    else:
        profile = picked

    profile = (profile or "").strip()

    if profile:
        n = len(storage.load_attempts(profile))
        st.caption(f"{n} attempt{'s' if n != 1 else ''} saved")

    st.divider()
    st.caption(
        "Saved on the server. A redeploy can clear it, so export from the "
        "Progress tab if you want to keep it for good."
    )


st.title("Interview Coach")
st.caption("Paste a job posting, or just type a role. Then practise answering and watch your scores move.")

tab_q, tab_p, tab_h = st.tabs(["1 · Questions", "2 · Practise", "3 · Progress"])


# ---------------- tab 1: questions ----------------
with tab_q:
    jd = st.text_area(
        "Job posting, or just a role title",
        value=st.session_state["jd"], height=220,
        placeholder='Paste the full posting for questions tied to it.\nOr type something like "Data Analyst" to get started.',
    )

    if st.button("Generate questions", type="primary"):
        if not jd.strip():
            st.warning("Type a role, or paste a posting.")
        else:
            mode = classify_input(jd)
            prompt = GROUNDED_PROMPT if mode == "posting" else ROLE_PROMPT
            with st.spinner("Reading the posting..." if mode == "posting" else "Thinking about this role..."):
                out = call_model(prompt + jd)
            st.session_state.update(jd=jd, mode=mode, raw_output=out,
                                    questions=extract_questions(out))

    if st.session_state["raw_output"]:
        if st.session_state["mode"] == "posting":
            st.success("**Grounded mode** — you gave a full posting, so every question cites the phrase it came from.")
        else:
            st.info("**Role mode** — you gave a role, not a posting, so these are the questions this role usually attracts. Paste the actual posting for questions tied to it.")
        st.markdown(st.session_state["raw_output"])
        if st.session_state["questions"]:
            st.caption(f"{len(st.session_state['questions'])} questions ready. Practise tab next.")


# ---------------- tab 2: practise ----------------
with tab_p:
    if not profile:
        st.warning("Enter a practice profile name in the sidebar first — that is what your attempts are saved under.")
    elif not st.session_state["questions"]:
        st.info("Generate questions first on the Questions tab.")
    else:
        choice = st.selectbox("Which question do you want to practise?",
                              st.session_state["questions"], index=0)

        # if they have answered this one before, show where they left off
        prior = [a for a in storage.load_attempts(profile) if a["question"] == choice]
        if prior:
            last = prior[-1]
            st.info(
                f"You have answered this {len(prior)} time{'s' if len(prior) != 1 else ''} before. "
                f"Last score **{last['overall']}/5**."
                + (f"  Weakest then: {last['weakest']}" if last["weakest"] else "")
            )

        answer = st.text_area(
            "Your answer", height=220,
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
                    scores = {d: data[d]["score"] for d in DIMENSIONS}
                    overall = storage.save_attempt(
                        profile, choice, answer, scores,
                        mode=st.session_state["mode"],
                        extras={k: data.get(k, "") for k in ("strongest", "weakest", "rewrite")},
                    )

                    prev = prior[-1]["overall"] if prior else None
                    if prev is not None:
                        st.subheader(f"Overall {overall} / 5   ({overall - prev:+.2f} vs last time)")
                    else:
                        st.subheader(f"Overall {overall} / 5")

                    cols = st.columns(4)
                    for col, d in zip(cols, DIMENSIONS):
                        delta = None
                        if prior:
                            delta = data[d]["score"] - prior[-1][d]
                        col.metric(d.capitalize(), f"{data[d]['score']}/5",
                                   delta=(f"{delta:+d}" if delta else None))

                    for d in DIMENSIONS:
                        st.markdown(f"**{d.capitalize()} — {data[d]['score']}/5**  \n{data[d]['reason']}")

                    if data.get("strongest"):
                        st.success("Strongest: " + data["strongest"])
                    if data.get("weakest"):
                        st.warning("Weakest: " + data["weakest"])
                    if data.get("rewrite"):
                        st.info("Try saying: " + data["rewrite"])

                    st.caption("Saved. See the Progress tab.")


# ---------------- tab 3: progress ----------------
with tab_h:
    if not profile:
        st.warning("Enter a practice profile name in the sidebar to see your history.")
    else:
        rows = storage.load_attempts(profile)

        if not rows:
            st.info(f"No attempts saved for **{profile}** yet.")
        else:
            df = pd.DataFrame(rows)
            df["attempt"] = range(1, len(df) + 1)
            df["when"] = pd.to_datetime(df["created_at"]).dt.strftime("%d %b %H:%M")

            # ---- headline ----
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Attempts", len(df))
            c2.metric("Questions", df["question"].nunique())
            c3.metric("Average", f"{df['overall'].mean():.2f}/5")
            if len(df) > 1:
                first_half = df["overall"].iloc[:max(1, len(df) // 2)].mean()
                second_half = df["overall"].iloc[len(df) // 2:].mean()
                c4.metric("Trend", f"{second_half:.2f}", delta=f"{second_half - first_half:+.2f}")
            else:
                c4.metric("Trend", "—")

            st.divider()

            # ---- overall trend ----
            st.subheader("Scores over time")
            st.line_chart(df.set_index("attempt")[DIMENSIONS + ["overall"]])

            # ---- where to focus ----
            means = df[DIMENSIONS].mean().sort_values()
            st.subheader("Where to focus")
            st.write(
                f"Your weakest dimension is **{means.index[0]}** at {means.iloc[0]:.2f}/5 average. "
                f"Strongest is **{means.index[-1]}** at {means.iloc[-1]:.2f}/5."
            )
            st.bar_chart(means)

            st.divider()

            # ---- per-question improvement: the point of saving anything ----
            st.subheader("Improvement on a single question")
            repeated = df["question"].value_counts()
            repeated = repeated[repeated > 1]

            if repeated.empty:
                st.info(
                    "Answer the same question twice and this is where you will see the two "
                    "attempts side by side. That comparison is the clearest signal of progress."
                )
            else:
                q = st.selectbox(
                    "Question practised more than once",
                    repeated.index.tolist(),
                    format_func=lambda s: short(s, 80),
                )
                sub = df[df["question"] == q].reset_index(drop=True)

                st.line_chart(sub.set_index("when")[DIMENSIONS + ["overall"]])

                first, last = sub.iloc[0], sub.iloc[-1]
                st.write(
                    f"First attempt **{first['overall']}/5** on {first['when']} → "
                    f"latest **{last['overall']}/5** on {last['when']}  "
                    f"(**{last['overall'] - first['overall']:+.2f}**)"
                )

                a, b = st.columns(2)
                with a:
                    st.caption(f"First attempt · {first['overall']}/5")
                    st.text_area("first", first["answer"], height=180,
                                 disabled=True, label_visibility="collapsed")
                with b:
                    st.caption(f"Latest attempt · {last['overall']}/5")
                    st.text_area("latest", last["answer"], height=180,
                                 disabled=True, label_visibility="collapsed")

            st.divider()

            # ---- full log ----
            st.subheader("Every attempt")
            view = df[["attempt", "when", "mode", "question", "overall"] + DIMENSIONS].copy()
            view["question"] = view["question"].map(lambda s: short(s, 70))
            st.dataframe(view, width="stretch", hide_index=True)

            with st.expander("Read a full answer"):
                pick = st.selectbox(
                    "Attempt", df["attempt"].tolist(),
                    format_func=lambda i: f"#{i} · {short(df.loc[i-1,'question'], 60)} · {df.loc[i-1,'overall']}/5",
                )
                row = df[df["attempt"] == pick].iloc[0]
                st.markdown(f"**{row['question']}**")
                st.text_area("answer", row["answer"], height=200,
                             disabled=True, label_visibility="collapsed")
                for label, key in [("Strongest", "strongest"), ("Weakest", "weakest"), ("Suggested", "rewrite")]:
                    if row.get(key):
                        st.caption(f"**{label}:** {row[key]}")

            st.divider()

            # ---- keep it safe ----
            st.subheader("Keep your history")
            d1, d2 = st.columns(2)
            with d1:
                st.download_button(
                    "Export (JSON)", storage.export_profile(profile),
                    file_name=f"interview_coach_{profile}.json", mime="application/json",
                )
                st.caption("Download this if you want your history to survive a redeploy.")
            with d2:
                st.download_button(
                    "Export (CSV)", df.to_csv(index=False).encode("utf-8"),
                    file_name=f"interview_coach_{profile}.csv", mime="text/csv",
                )

    # import works even with no profile loaded
    st.divider()
    up = st.file_uploader("Restore a previous export (JSON)", type="json")
    if up is not None and st.button("Import"):
        try:
            n = storage.import_profile(up.getvalue(), profile or None)
            st.success(f"Imported {n} attempt{'s' if n != 1 else ''}.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not import: {e}")
