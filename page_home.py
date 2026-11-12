import streamlit as st

import core
import ui

core.inject_css()
core.init_state()

st.markdown(
    ui.hero(
        "Interview questions that show their working.",
        "Paste the job posting you are preparing for. Every question comes back "
        "with the line of the posting it was drawn from, and every one of those "
        "lines is checked against your text before you see it.",
    ),
    unsafe_allow_html=True,
)

st.markdown(
    ui.specimen(
        "Tell me about a dashboard you built that people actually used.",
        "Build and maintain dashboards in Tableau covering retention, churn and "
        "expansion revenue",
        "a named dashboard, who used it, and what decision it changed",
    ),
    unsafe_allow_html=True,
)

if st.button("Start with your posting", type="primary"):
    st.switch_page("page_practice.py")

st.markdown("<div style='height:2.4rem'></div>", unsafe_allow_html=True)

st.markdown(
    ui.section(
        "Why the quote is there",
        "Ask any chatbot for interview questions and it will give you six good ones. "
        "Some will come from the posting you pasted. Some will come from what the "
        "model assumes a job with that title involves. Nothing on the screen tells "
        "you which is which, and you find out in the interview. "
        "<b>So each question here carries the line it came from, and that line is "
        "searched for in your posting before the question is shown.</b> When a quote "
        "cannot be found, the question is marked rather than quietly left in.",
    ),
    unsafe_allow_html=True,
)

st.markdown(
    ui.section(
        "What you paste changes what you get",
        "A full posting and a two-word job title need different handling, so the app "
        "looks at what you gave it and says which way it went.",
    ),
    unsafe_allow_html=True,
)
st.markdown(ui.routing_rows(), unsafe_allow_html=True)

st.markdown(
    ui.section(
        "Then you answer them",
        "Pick a question, say your answer out loud, and type roughly what you said. "
        "It comes back scored out of five on how specific it was, how it was "
        "structured, what evidence you gave and whether you answered the question "
        "asked, each with the reason. Answer the same question again next week and "
        "both attempts sit side by side, so the thing you are looking at is the "
        "change rather than a single score.",
    ),
    unsafe_allow_html=True,
)

st.markdown(
    ui.section(
        "What it will not do",
        "Scores come from a language model reading your text, not from a marker who "
        "knows the job. Two runs on the same answer can differ by a point, so the "
        "trend across attempts is worth more than any single number. Your history is "
        "kept on the server and a redeploy clears it, so there is a download button "
        "on the Progress tab.",
    ),
    unsafe_allow_html=True,
)

st.markdown("<div style='height:1.4rem'></div>", unsafe_allow_html=True)

if st.button("Start", type="primary", key="start_bottom"):
    st.switch_page("page_practice.py")
