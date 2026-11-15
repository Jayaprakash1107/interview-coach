"""Known-answer tests for the evaluation scoring.

The eval produces the number this project's central claim rests on, so the
scoring itself has to be trustworthy. These cases are hand-built responses
whose correct score is known in advance, including the three that matter:

  - a citation wrapped across two lines in the source, which must verify,
    because the wrap is formatting and not a change of wording
  - a citation that appears nowhere in the posting, which must fail
  - a citation that paraphrases the posting, which must also fail, since the
    claim being checked is that the quote is verbatim

Run:  python eval/test_scoring.py
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.run_eval import requirement_lines, score_run  # noqa: E402

POSTING = (ROOT / "eval/postings/01_data_analyst.txt").read_text(encoding="utf-8")
FIXTURES = json.loads(
    (ROOT / "eval/fixtures/known_answers.json").read_text(encoding="utf-8"))
GOOD = next(f["raw"] for f in FIXTURES if f["arm"] == "grounded")
BROKEN = next(f["raw"] for f in FIXTURES if f["arm"] == "naive")

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")
    else:
        print(f"  ok    {label}")


def main():
    print("requirement extraction")
    check("bulleted requirement lines found", len(requirement_lines(POSTING)), 8)

    print("\nscoring a response with known defects")
    s = score_run(POSTING, GOOD)
    check("questions parsed", s["parsed"], 6)
    check("citations offered", s["cited"], 6)
    check("citations that verify", s["verified"], 4)
    check("generic questions flagged", s["generic_questions"], 1)
    check("requirements covered", s["requirements_covered"], 4)

    v = [r["verified"] for r in s["rows"]]
    check("line-wrapped citation verifies", v[0], True)
    check("exact citation verifies", v[1], True)
    check("hallucinated citation rejected", v[2], False)
    check("paraphrased citation rejected", v[3], False)

    print("\nscoring an unparseable response")
    b = score_run(POSTING, BROKEN)
    check("flagged as a parse failure", b["parse_failed"], True)
    check("questions parsed", b["parsed"], 0)
    check("scores 0 rather than abstaining", b["grounded_rate"], 0.0)

    print()
    if failures:
        print(f"{len(failures)} FAILED")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
