"""Groundwork — entry point.

Two pages: what the tool is, and the tool itself. Everything shared lives in
core.py so neither page has to own what the other needs.
"""

import streamlit as st

st.set_page_config(
    page_title="Groundwork",
    page_icon="assets/favicon.png",
    layout="centered",
    initial_sidebar_state="collapsed",
)

pages = [
    st.Page("page_home.py", title="What this is", default=True),
    st.Page("page_practice.py", title="Practice"),
]

st.navigation(pages).run()
