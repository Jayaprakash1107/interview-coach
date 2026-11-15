import pandas as pd
import streamlit as st

import core
import storage
import ui

core.inject_css()
core.init_state()
storage.init_db()

DIMENSIONS = core.DIMENSIONS
GROUNDED_PROMPT, ROLE_PROMPT, _ = core.prompts()
GAPS_PROMPT = core.gaps_prompt()


# ----------------------------------------------------------------------
# sidebar
# ----------------------------------------------------------------------
with st.sidebar:
    st.subheader("Who is practicing")
    st.caption("Attempts are saved under this name, so you can pick up where you left off.")

    existing = [p for p, _ in storage.list_profiles()]
    picked = st.selectbox("Saved", ["New name"] + existing, index=0) if existing else "New name"
    profile = st.text_input("Name", value="", placeholder="jay") if picked == "New name" else picked
    profile = (profile or "").strip()
    st.session_state["profile"] = profile

    if profile:
        n = len(storage.load_attempts(profile))
        st.caption(f"{n} answer{'s' if n != 1 else ''} scored so far")

    st.divider()
    st.caption("History lives on the server and can be cleared by a redeploy. "
               "Download it from Progress to keep it.")


st.markdown(ui.masthead(), unsafe_allow_html=True)

tab_q, tab_p, tab_h = st.tabs(["Questions", "Practice", "Progress"])


# ---------------- questions ----------------
with tab_q:
    jd = st.text_area(
        "The job you are interviewing for",
        value=st.session_state["jd"], height=200,
        placeholder="Paste the posting here. A job title on its own works too, "
                    "though the questions will be less specific.",
    )

    b1, b2, _ = st.columns([2, 2, 3])
    with b1:
        go = st.button("Generate questions", type="primary")
    with b2:
        if st.button("Use a sample posting"):
            st.session_state["jd"] = core.EXAMPLE_POSTING
            st.rerun()

    if go:
        if not jd.strip():
            st.warning("Paste a posting, or type the role you are going for.")
        else:
            mode = core.classify_input(jd)
            prompt = GROUNDED_PROMPT if mode == "posting" else ROLE_PROMPT
            with st.spinner("Reading the posting..." if mode == "posting"
                            else "Thinking about this role..."):
                out = core.call_model(prompt + jd)
            st.session_state.update(jd=jd, mode=mode, raw_output=out,
                                    questions=core.extract_questions(out),
                                    gap_output="")

    if st.session_state["raw_output"]:
        mode = st.session_state["mode"]
        st.markdown(ui.mode_strip(mode), unsafe_allow_html=True)

        parsed = ui.parse_questions(st.session_state["raw_output"])

        if not parsed:
            # format drifted - show the raw output rather than an empty page
            st.markdown(st.session_state["raw_output"])
        else:
            results = {}
            if mode == "posting":
                cited = [q for q in parsed if q["cite"]]
                results = {id(q): core.cite_found(q["cite"], st.session_state["jd"])
                           for q in cited}
                if cited:
                    ok = sum(1 for v in results.values() if v)
                    st.markdown(ui.check_strip(ok, len(cited)), unsafe_allow_html=True)

            for q in parsed:
                st.markdown(ui.question_card(q, verified=results.get(id(q))),
                            unsafe_allow_html=True)

            st.caption("Pick one of these on the Practice tab and answer it.")

            # ---------- coverage ----------
            # Verification is per question. This is the view across the whole
            # posting: which requirements got a question, and which did not.
            if mode == "posting":
                rows, covered, total = core.coverage(st.session_state["jd"], parsed)
                if total:
                    st.markdown(ui.coverage_block(rows, covered, total),
                                unsafe_allow_html=True)

                    gaps = [r["line"] for r in rows if not r["nums"]]
                    if gaps:
                        label = (f"Write questions for the {len(gaps)} that "
                                 f"{'were' if len(gaps) != 1 else 'was'} missed")
                        if st.button(label, type="primary", key="fill_gaps"):
                            listed = "\n".join(f"- {g}" for g in gaps)
                            prompt = (GAPS_PROMPT + "FULL POSTING:\n"
                                      + st.session_state["jd"]
                                      + "\n\nUNCOVERED LINES:\n" + listed)
                            with st.spinner("Looking at what was missed..."):
                                out = core.call_model(prompt)
                            st.session_state["gap_output"] = out
                            st.session_state["questions"] = (
                                st.session_state["questions"]
                                + core.extract_questions(out))
                            st.rerun()

            # ---------- questions written for the gaps ----------
            if st.session_state["gap_output"]:
                extra = ui.parse_questions(st.session_state["gap_output"])
                st.markdown(ui.section(
                    "Questions for what was missed",
                    "These were written against the requirements no question had "
                    "reached. They are checked the same way as the rest."),
                    unsafe_allow_html=True)
                if not extra:
                    st.markdown(st.session_state["gap_output"])
                else:
                    extra_ok = {id(q): core.cite_found(q["cite"],
                                                       st.session_state["jd"])
                                for q in extra if q["cite"]}
                    for q in extra:
                        st.markdown(
                            ui.question_card(q, verified=extra_ok.get(id(q))),
                            unsafe_allow_html=True)


# ---------------- practice ----------------
with tab_p:
    if not profile:
        st.info("Add a name in the sidebar first. That is how your answers are saved.")
    elif not st.session_state["questions"]:
        st.info("Generate some questions first.")
    else:
        choice = st.selectbox("Question", st.session_state["questions"], index=0)

        prior = [a for a in storage.load_attempts(profile) if a["question"] == choice]
        if prior:
            last = prior[-1]
            msg = (f"You have answered this {len(prior)} time"
                   f"{'s' if len(prior) != 1 else ''}. Last time you scored "
                   f"{last['overall']} out of 5.")
            if last["weakest"]:
                msg += f" {last['weakest']}"
            st.caption(msg)

        answer = st.text_area(
            "Your answer", height=210,
            placeholder="Say it out loud first, then type roughly what you said. "
                        "Rough is fine — that is closer to how it will come out.",
            key="answer_box",
        )
        words = len(answer.split())
        st.caption(f"{words} words")

        if st.button("Score this answer", type="primary"):
            if words < 10:
                st.warning("A sentence or two more and there is something to score.")
            else:
                with st.spinner("Reading your answer..."):
                    data, raw = core.score_answer(choice, answer)

                if not data:
                    st.error("The scoring came back in a form this could not read. Try again.")
                    with st.expander("What came back"):
                        st.code(raw)
                else:
                    scores = {d: data[d]["score"] for d in DIMENSIONS}
                    overall = storage.save_attempt(
                        profile, choice, answer, scores,
                        mode=st.session_state["mode"],
                        extras={k: data.get(k, "") for k in ("strongest", "weakest", "rewrite")},
                    )

                    prev = prior[-1]["overall"] if prior else None
                    st.markdown(ui.overall_block(overall, prev), unsafe_allow_html=True)

                    for d in DIMENSIONS:
                        delta = (data[d]["score"] - prior[-1][d]) if prior else None
                        st.markdown(
                            ui.dimension_block(d.capitalize(), data[d]["score"],
                                               data[d]["reason"], delta or None),
                            unsafe_allow_html=True,
                        )

                    if data.get("rewrite"):
                        st.markdown(ui.rewrite_block(data["rewrite"]), unsafe_allow_html=True)

                    st.caption("Saved. The Progress tab shows how this compares "
                               "with your earlier tries.")


# ---------------- progress ----------------
with tab_h:
    if not profile:
        st.info("Add a name in the sidebar to see your history.")
    else:
        rows = storage.load_attempts(profile)

        if not rows:
            st.info(f"Nothing saved for {profile} yet. Score an answer and it shows up here.")
        else:
            df = pd.DataFrame(rows)
            df["attempt"] = range(1, len(df) + 1)
            df["when"] = pd.to_datetime(df["created_at"]).dt.strftime("%d %b %H:%M")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Answers", len(df))
            c2.metric("Questions", df["question"].nunique())
            c3.metric("Average", f"{df['overall'].mean():.2f}")
            if len(df) > 1:
                half = max(1, len(df) // 2)
                early, late = df["overall"].iloc[:half].mean(), df["overall"].iloc[half:].mean()
                c4.metric("Lately", f"{late:.2f}", delta=f"{late - early:+.2f}")
            else:
                c4.metric("Lately", "—")

            st.divider()

            st.subheader("Every answer you have scored")
            st.line_chart(df.set_index("attempt")[DIMENSIONS + ["overall"]])

            means = df[DIMENSIONS].mean().sort_values()
            st.subheader("What to work on")
            st.write(
                f"**{means.index[0].capitalize()}** is your weakest at "
                f"{means.iloc[0]:.2f} out of 5. **{means.index[-1].capitalize()}** "
                f"is your strongest at {means.iloc[-1]:.2f}."
            )
            st.bar_chart(means)

            st.divider()

            st.subheader("The same question, twice")
            repeated = df["question"].value_counts()
            repeated = repeated[repeated > 1]

            if repeated.empty:
                st.caption("Answer a question you have already done and both attempts "
                           "appear here side by side. That comparison is the clearest "
                           "sign of progress.")
            else:
                q = st.selectbox("Question", repeated.index.tolist(),
                                 format_func=lambda s: core.short(s, 80))
                sub = df[df["question"] == q].reset_index(drop=True)
                first, last = sub.iloc[0], sub.iloc[-1]

                st.line_chart(sub.set_index("when")[DIMENSIONS + ["overall"]])
                st.write(
                    f"{first['overall']} on {first['when']}, "
                    f"{last['overall']} on {last['when']} — "
                    f"**{last['overall'] - first['overall']:+.2f}**"
                )

                a, b = st.columns(2)
                with a:
                    st.markdown(ui.answer_panel("First try", first["overall"], first["answer"]),
                                unsafe_allow_html=True)
                with b:
                    st.markdown(ui.answer_panel("Most recent", last["overall"], last["answer"]),
                                unsafe_allow_html=True)

            st.divider()

            st.subheader("All of it")
            view = df[["attempt", "when", "mode", "question", "overall"] + DIMENSIONS].copy()
            view["question"] = view["question"].map(lambda s: core.short(s, 70))
            st.dataframe(view, width="stretch", hide_index=True)

            with st.expander("Read one back in full"):
                pick = st.selectbox(
                    "Answer", df["attempt"].tolist(),
                    format_func=lambda i: f"{core.short(df.loc[i-1,'question'], 58)} "
                                          f"— {df.loc[i-1,'overall']}/5",
                )
                row = df[df["attempt"] == pick].iloc[0]
                st.markdown(f"**{row['question']}**")
                st.markdown(ui.answer_panel(row["when"], row["overall"], row["answer"]),
                            unsafe_allow_html=True)
                for label, key in [("Strongest", "strongest"), ("Weakest", "weakest"),
                                   ("Suggested", "rewrite")]:
                    if row.get(key):
                        st.caption(f"**{label}:** {row[key]}")

            st.divider()

            st.subheader("Keep a copy")
            st.caption("A redeploy clears the server's copy. Download yours to be safe.")
            d1, d2 = st.columns(2)
            with d1:
                st.download_button("Download as JSON", storage.export_profile(profile),
                                   file_name=f"groundwork_{profile}.json",
                                   mime="application/json")
            with d2:
                st.download_button("Download as CSV", df.to_csv(index=False).encode("utf-8"),
                                   file_name=f"groundwork_{profile}.csv", mime="text/csv")

    st.divider()
    up = st.file_uploader("Restore from a download", type="json")
    if up is not None and st.button("Restore"):
        try:
            n = storage.import_profile(up.getvalue(), profile or None)
            st.success(f"Restored {n} answer{'s' if n != 1 else ''}.")
            st.rerun()
        except Exception as e:
            st.error(f"That file could not be read: {e}")
