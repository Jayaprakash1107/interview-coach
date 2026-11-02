# Interview Coach

Paste a job posting, get interview questions that are provably tied to it, then practise answering and watch your scores move across sessions.

Built as an IT capstone project (M.S. Information Technology, Generative AI concentration, Clark University).

**Live app:** _add your Streamlit URL here_

---

## The problem

Candidates preparing for a specific interview fall back on generic question lists that ignore the posting, or paste the posting into a general chatbot and get plausible-sounding questions with no way to tell whether any of them came from the posting at all.

The second failure is the interesting one. A language model will happily produce six confident, well-written questions about a role it has partly invented, and nothing on screen distinguishes those from questions grounded in the actual text.

## What this does differently

**Every question cites its source, and the app checks the citation.**

The generation prompt requires each question to quote the exact phrase from the posting it was derived from, and forbids asking anything that cannot be quoted. That is a claim. The app then verifies it: each cited phrase is searched for in the posting the user supplied, and the result is reported as `6 of 6 citations verified`, with a warning on any that cannot be found verbatim.

Formatting differences are normalised — case, whitespace, smart quotes, dashes. Wording is not. A paraphrase fails the check, which is the point.

**Input is routed, not assumed.**

A full posting and a two-word role title need different handling. A rule — word count plus job-ad phrase detection — sends each down a different path:

| Input | Mode | Behaviour |
|---|---|---|
| Full posting | Grounded | Every question cites an exact phrase; citations verified |
| Role title only | Role | Typical questions for that role, labelled as not posting-specific |

This is a rule rather than a model call on purpose: it is instant, costs nothing, and returns the same answer every time. The user is told which mode fired, so the behaviour is predictable.

**Practice is scored and remembered.**

Answer a question and it is scored 1–5 on specificity, structure, evidence and relevance, each with a reason that quotes what you actually wrote, plus one concrete rewrite suggestion. Attempts are stored under a practice profile, so answering the same question twice shows both attempts side by side with the score delta between them.

That last part is the thing a chat window cannot do. A chatbot can score one answer. It cannot tell you that your evidence scores have averaged 2.3 across six attempts while your structure improved from 2 to 4.

---

## Running it

```bash
git clone https://github.com/Jayaprakash1107/interview-coach.git
cd interview-coach
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a `.env` file with a free Groq key from [console.groq.com/keys](https://console.groq.com/keys):

```
GROQ_API_KEY=gsk_your_key_here
```

```bash
streamlit run app.py
```

Deployed on Streamlit Community Cloud, with the key supplied through Secrets rather than `.env`.

---

## How it is built

| File | Responsibility |
|---|---|
| `app.py` | UI, input routing, grounding verification |
| `storage.py` | SQLite persistence, export and import |
| `prompt.txt` | Grounded generation — full posting in, cited questions out |
| `prompt_role.txt` | Role mode — role title in, typical questions out, no citations |
| `prompt_scoring.txt` | Answer scoring against the four-dimension rubric |

Prompts live in separate text files rather than inside the Python. They are the part that changes most often, and keeping them out of the code means iterating on them without touching logic.

**Stack:** Streamlit, Groq (`openai/gpt-oss-120b`), SQLite, pandas. Runs entirely on free tiers.

---

## Known limitations

**History is not durable on the hosted version.** Streamlit Community Cloud rebuilds the container on redeploy and after idle periods, which deletes the SQLite file. Export to JSON is provided as the workaround, and import restores a previous export without duplicating rows. Durable storage needs accounts and a hosted database, which is out of scope for this version.

**Scoring is a language model judging text, not ground truth.** The rubric constrains it and the prompt explicitly instructs against inflated scores, but two runs on the same answer can differ by a point. The value is in the trend across attempts, not in any single score.

**Output varies between runs.** The same posting produces different questions on different generations. This is inherent to the approach and limits reproducibility.

**No accounts.** A practice profile is a name typed into a box. Anyone using the same name on the same deployment sees the same history. Fine for single-user practice, not for anything shared.

---

## Changes since the first version

| Version | Change | Why |
|---|---|---|
| v0.1 | Posting in, six questions out | Baseline. One unconstrained prompt; output was generic. |
| v0.2 | Grounding: every question must quote a phrase from the posting | Generic questions were the core quality problem, and a constraint fixed what prompt-tuning did not. |
| v0.2 | Answer guidance per question | Knowing the question is not knowing what a good answer contains. |
| v0.3 | Role mode plus deterministic router | A two-word role title previously produced a refusal. Now it produces useful output, honestly labelled. |
| v0.3 | Answer scoring against a four-dimension rubric | Turned a question generator into something that responds to what you say. |
| v0.4 | SQLite persistence and per-question comparison | Progress across sessions is the thing a stateless chat cannot offer. |
| v0.4 | Automatic grounding verification | The app made a claim about its own output; now it checks it. |
