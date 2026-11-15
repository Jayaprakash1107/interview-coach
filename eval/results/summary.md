# Groundwork — grounding evaluation

Run 2026-11-15 01:16 UTC · model `openai/gpt-oss-120b` · 12 postings

## Headline

| Metric | Grounded | Naive |
|---|---|---|
| Questions carrying a verified citation | 89% | 71% |
| Offered citations that were real | 97% | 71% |
| Posting requirements covered | 57% | 48% |
| Generic questions per posting | 0.00 | 0.00 |
| Responses the parser could not read | 0 | 0 |
| Questions produced | 6.0 | 6.0 |

## Per posting

| Posting | Grounded grounded | Naive grounded |
|---|---|---|
| 01_data_analyst | 4/6 | 4/6 |
| 02_ml_engineer | 6/6 | 5/6 |
| 03_backend_engineer | 6/6 | 5/6 |
| 04_product_manager | 0/6 | 5/6 |
| 05_ux_designer | 6/6 | 6/6 |
| 06_devops_sre | 6/6 | 6/6 |
| 07_data_engineer | 6/6 | 6/6 |
| 08_marketing_analyst | 6/6 | 4/6 |
| 09_qa_engineer | 6/6 | 3/6 |
| 10_technical_writer | 6/6 | 1/6 |
| 11_research_scientist | 6/6 | 5/6 |
| 12_customer_success | 6/6 | 1/6 |

## How to read this

*Questions carrying a verified citation* is the number that matches what a
person using the app sees: of every question put in front of them, the share
whose quoted line was found in the posting they pasted.

*Offered citations that were real* separates two different failures. A model
can quote nothing at all, or it can quote something that was never there.
Only the second is a hallucination.

Both arms were parsed and verified by the same functions the app calls
(`ui.parse_questions`, `core.cite_found`), so the difference between them is
the prompt, not the measurement.

The postings are written to span roles, seniorities and lengths rather than
scraped, so they are representative inputs, not a random sample of the market.
The measured outputs are real model runs.
