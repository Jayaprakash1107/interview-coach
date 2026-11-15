# Evaluating the grounding claim

Groundwork's claim is narrow and testable: **every interview question it shows
quotes a line that actually appears in the posting you pasted.** Inside the app
that claim is checked one posting at a time. This directory checks it across a
fixed set of postings and reports the result as a number.

## What is measured

| Metric | What it means |
|---|---|
| **Questions carrying a verified citation** | Of every question put in front of a user, the share whose quoted line was found in the posting. This is the number that matches what a person experiences. |
| **Offered citations that were real** | Of the citations the model chose to give, how many existed. This separates *quoting nothing* from *quoting something that was never there*. Only the second is a hallucination. |
| **Posting requirements covered** | Of the posting's bulleted requirements, how many at least one verified question drew on. A high grounding rate with low coverage means the questions are honest but clustered. |
| **Generic questions** | Occurrences of the phrasings the prompt explicitly forbids ("tell me about yourself"). A prompt can produce verifiable citations and still ask questions that would suit any job. |
| **Responses the parser could not read** | Format drift. In the app this triggers the raw-markdown fallback, so the user still sees something, but the per-question verification is lost. |

## The ablation

The same postings run through two prompts:

- **Grounded** — the prompt the app ships (`prompt.txt`), with its hard rules:
  quote or don't ask, never infer, no generic questions.
- **Naive** — `prompt_naive.txt`, which asks for the *same output format*,
  including a citation line, but none of the discipline.

Holding the output format constant is deliberate. If the naive arm produced a
different shape, the comparison would partly measure parsing rather than
grounding. Both arms are parsed by `ui.parse_questions` and verified by
`core.cite_found` — the functions the running app calls, not reimplementations.
The difference between the arms is therefore the prompt.

## Running it

```bash
python eval/run_eval.py                 # both arms, 12 postings, 24 model calls
python eval/run_eval.py --arm grounded  # one arm
python eval/run_eval.py --offline eval/results/raw_YYYYMMDD_HHMM.json
```

Needs `GROQ_API_KEY` in `.env`. Takes a few minutes; the free tier is
rate-limited, so there is a pause between calls and a backoff on failure.

Outputs land in `eval/results/`:

- `raw_<timestamp>.json` — every model response, kept so any number in the
  summary can be traced back to the text it came from
- `summary.md` — the tables
- `comparison.png` — the chart (needs `matplotlib`; skipped if absent)

`--offline` re-scores a saved run without spending API calls, which is how to
re-measure after changing the scoring without re-querying the model.

## Testing the scoring

```bash
python eval/test_scoring.py
```

The eval produces the number the project's claim rests on, so the scoring is
itself tested against hand-built responses with known-correct scores. The three
cases that matter:

- a citation **wrapped across two lines** in the source must verify — the wrap
  is formatting, not a change of wording
- a citation that **appears nowhere** in the posting must fail
- a citation that **paraphrases** the posting must also fail, because the claim
  being checked is that the quote is verbatim

That last one is the reason normalization is restricted to case, whitespace,
smart quotes and dash shape. Any normalization that reached wording would make
the check pass on text the posting never contained, and the number would stop
meaning anything.

## Limitations

Stated plainly, because they bound what the result supports:

- **The postings are written, not scraped.** They span roles, seniorities and
  lengths deliberately rather than sampling the market, so they are
  representative inputs, not a random sample. The *outputs* measured are real
  model runs. A scraped set would strengthen the external validity.
- **Verification is exact substring matching.** It proves a quote is present.
  It does not prove the question is a *good* question about that line, which is
  a judgement no automatic check here makes.
- **Coverage uses bulleted lines only.** Requirements stated in prose
  paragraphs are not counted, so coverage is measured against the structured
  part of a posting.
- **One model, one temperature.** Results are specific to the model in
  `core.MODEL` at the temperature `core.call_model` uses. Re-running will vary
  slightly; the raw JSON is kept so any run can be re-examined.
- **No human rating.** Grounding is checked mechanically. Whether grounded
  questions are more *useful* in a real interview is what the user testing is
  for, not this.
