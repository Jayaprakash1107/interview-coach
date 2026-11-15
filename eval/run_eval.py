"""Measure whether Groundwork's citations are actually grounded.

The app's central claim is that every question quotes a line that really
appears in the posting. In the app that claim is checked one posting at a
time, by the person using it. This runs the same check over a fixed set of
postings and counts, so the claim becomes a number.

It is an ablation as well as a measurement. The same postings go through two
prompts - the one the app ships, and a naive one that asks for the same output
format without any of the grounding discipline - and both are parsed and
verified by exactly the same code the app uses. The difference between the two
is what the prompt engineering is worth.

Nothing here is imported by the app. Running it cannot affect the app.

    python eval/run_eval.py                  # both arms, needs GROQ_API_KEY
    python eval/run_eval.py --arm grounded   # one arm only
    python eval/run_eval.py --offline DIR    # re-score saved runs, no API calls

Results land in eval/results/.
"""

import argparse
import json
import os
import pathlib
import re
import statistics
import sys
import time
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import core  # noqa: E402  - the real pipeline, not a copy of it
import ui    # noqa: E402

HERE = ROOT / "eval"
POSTINGS = HERE / "postings"
RESULTS = HERE / "results"

# Questions the app's prompt explicitly forbids. Counting them is a second,
# independent signal: a prompt can produce verifiable citations and still ask
# questions that would suit any job at all.
GENERIC = [
    "tell me about yourself", "what are your strengths", "what are your weaknesses",
    "why this company", "why do you want to work here", "where do you see yourself",
    "greatest weakness", "describe yourself in", "why should we hire you",
]


# ----------------------------------------------------------------------
# metrics
# ----------------------------------------------------------------------
# Coverage now lives in core, so the eval measures the same function the app
# calls rather than a second copy that could drift from it.
requirement_lines = core.requirement_lines


def score_run(posting, raw_output):
    """Everything measurable about one model response."""
    parsed = ui.parse_questions(raw_output)
    reqs = requirement_lines(posting)
    norm_reqs = [core.normalize(r) for r in reqs]

    rows, covered = [], set()
    for q in parsed:
        cite = q["cite"]
        ok = core.cite_found(cite, posting) if cite else False
        if ok:
            nc = core.normalize(cite)
            for i, nr in enumerate(norm_reqs):
                if nc in nr or nr in nc:
                    covered.add(i)
        rows.append({"question": q["text"], "cite": cite, "verified": ok})

    text = " ".join(q["text"].lower() for q in parsed)
    generic = sum(1 for g in GENERIC if g in text)

    n = len(parsed)
    cited = sum(1 for r in rows if r["cite"])
    verified = sum(1 for r in rows if r["verified"])
    return {
        "parsed": n,
        "cited": cited,
        "verified": verified,
        # of the citations the model offered, how many were real
        "precision": verified / cited if cited else None,
        # Of all questions shown to a user, how many carry a real citation.
        # This is the number that matches what a person experiences. A response
        # the parser cannot read scores 0, not n/a: the user got no grounded
        # questions out of it, and averaging it away would hide the failure.
        "grounded_rate": verified / n if n else 0.0,
        "requirements": len(reqs),
        "requirements_covered": len(covered),
        "coverage": len(covered) / len(reqs) if reqs else None,
        "generic_questions": generic,
        "parse_failed": n == 0,
        "rows": rows,
    }


# ----------------------------------------------------------------------
# running
# ----------------------------------------------------------------------
def load_postings():
    files = sorted(POSTINGS.glob("*.txt"))
    if not files:
        sys.exit(f"No postings found in {POSTINGS}")
    return [(f.stem, f.read_text(encoding="utf-8")) for f in files]


def prompt_for(arm):
    if arm == "grounded":
        return (ROOT / "prompt.txt").read_text(encoding="utf-8")
    return (HERE / "prompt_naive.txt").read_text(encoding="utf-8")


def call_with_retry(prompt, attempts=4):
    """Groq's free tier rate-limits. Back off rather than lose the run."""
    for i in range(attempts):
        try:
            return core.call_model(prompt), None
        except Exception as e:                      # noqa: BLE001
            msg = str(e)
            if i == attempts - 1:
                return None, msg
            wait = 5 * (2 ** i)
            print(f"      retry in {wait}s ({msg[:70]})")
            time.sleep(wait)
    return None, "exhausted"


def run(arms, pause):
    if not core.get_key():
        sys.exit("No GROQ_API_KEY found. Put it in .env next to app.py.")
    postings = load_postings()
    print(f"{len(postings)} postings x {len(arms)} arm(s) = "
          f"{len(postings)*len(arms)} model calls\n")

    out = []
    for name, posting in postings:
        print(f"  {name}")
        for arm in arms:
            raw, err = call_with_retry(prompt_for(arm) + posting)
            if err:
                print(f"      {arm}: FAILED - {err[:70]}")
                out.append({"posting": name, "arm": arm, "error": err})
                continue
            s = score_run(posting, raw)
            s.update(posting=name, arm=arm, raw=raw)
            out.append(s)
            gr = s["grounded_rate"]
            print(f"      {arm:9} {s['verified']}/{s['parsed']} grounded"
                  + (f"  ({gr:.0%})" if gr is not None else "  (parse failed)"))
            time.sleep(pause)
    return out


def rescore_offline(d):
    """Re-score saved runs. Used to test the scoring without spending calls."""
    runs = json.loads(pathlib.Path(d).read_text(encoding="utf-8"))
    postings = dict(load_postings())
    out = []
    for r in runs:
        if r.get("error"):
            out.append(r)
            continue
        s = score_run(postings[r["posting"]], r["raw"])
        s.update(posting=r["posting"], arm=r["arm"], raw=r["raw"])
        out.append(s)
    return out


# ----------------------------------------------------------------------
# reporting
# ----------------------------------------------------------------------
def agg(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return statistics.mean(vals) if vals else None


def pct(v):
    return "n/a" if v is None else f"{v:.0%}"


def summarise(results):
    arms = [a for a in ("grounded", "naive") if any(r["arm"] == a for r in results)]
    lines = ["# Groundwork — grounding evaluation", "",
             f"Run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · "
             f"model `{core.MODEL}` · {len(load_postings())} postings", ""]

    lines += ["## Headline", "",
              "| Metric | " + " | ".join(a.title() for a in arms) + " |",
              "|---|" + "---|" * len(arms)]

    def row(label, fn):
        return f"| {label} | " + " | ".join(
            fn([r for r in results if r["arm"] == a and not r.get("error")])
            for a in arms) + " |"

    lines += [
        row("Questions carrying a verified citation", lambda rs: pct(agg(rs, "grounded_rate"))),
        row("Offered citations that were real", lambda rs: pct(agg(rs, "precision"))),
        row("Posting requirements covered", lambda rs: pct(agg(rs, "coverage"))),
        row("Generic questions per posting",
            lambda rs: f"{agg(rs, 'generic_questions'):.2f}" if rs else "n/a"),
        row("Responses the parser could not read",
            lambda rs: str(sum(1 for r in rs if r["parse_failed"]))),
        row("Questions produced", lambda rs: f"{agg(rs, 'parsed'):.1f}" if rs else "n/a"),
    ]

    lines += ["", "## Per posting", "",
              "| Posting | " + " | ".join(f"{a.title()} grounded" for a in arms) + " |",
              "|---|" + "---|" * len(arms)]
    for name, _ in load_postings():
        cells = []
        for a in arms:
            m = next((r for r in results if r["posting"] == name and r["arm"] == a), None)
            cells.append("error" if not m or m.get("error")
                         else f"{m['verified']}/{m['parsed']}")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    lines += ["", "## How to read this", "",
              "*Questions carrying a verified citation* is the number that matches what a",
              "person using the app sees: of every question put in front of them, the share",
              "whose quoted line was found in the posting they pasted.",
              "",
              "*Offered citations that were real* separates two different failures. A model",
              "can quote nothing at all, or it can quote something that was never there.",
              "Only the second is a hallucination.",
              "",
              "Both arms were parsed and verified by the same functions the app calls",
              "(`ui.parse_questions`, `core.cite_found`), so the difference between them is",
              "the prompt, not the measurement.",
              "",
              "The postings are written to span roles, seniorities and lengths rather than",
              "scraped, so they are representative inputs, not a random sample of the market.",
              "The measured outputs are real model runs.",
              ""]
    return "\n".join(lines)


def chart(results, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    arms = [a for a in ("grounded", "naive") if any(r["arm"] == a for r in results)]
    metrics = [("grounded_rate", "Questions with a\nverified citation"),
               ("precision", "Offered citations\nthat were real"),
               ("coverage", "Posting requirements\ncovered")]
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    w, x = 0.36, range(len(metrics))
    colours = {"grounded": "#1D6B4C", "naive": "#9C3225"}
    for i, a in enumerate(arms):
        rs = [r for r in results if r["arm"] == a and not r.get("error")]
        vals = [(agg(rs, k) or 0) * 100 for k, _ in metrics]
        pos = [p + (i - (len(arms) - 1) / 2) * w for p in x]
        bars = ax.bar(pos, vals, w, label=a.title(), color=colours.get(a, "#5A7183"))
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.0f}%",
                    ha="center", fontsize=9, color="#16303F")
    ax.set_xticks(list(x))
    ax.set_xticklabels([lbl for _, lbl in metrics], fontsize=9)
    ax.set_ylim(0, 112)
    ax.set_ylabel("Mean across postings (%)", fontsize=9)
    ax.set_title("Grounded prompt vs naive prompt, same postings and same checks",
                 fontsize=10.5, color="#16303F")
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.18)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["grounded", "naive"],
                    help="run only one arm (default: both)")
    ap.add_argument("--offline", metavar="RAW_JSON",
                    help="re-score a saved raw_*.json instead of calling the API")
    ap.add_argument("--pause", type=float, default=1.5,
                    help="seconds between calls, to stay under the rate limit")
    a = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    results = (rescore_offline(a.offline) if a.offline
               else run([a.arm] if a.arm else ["grounded", "naive"], a.pause))

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    raw_path = RESULTS / f"raw_{stamp}.json"
    raw_path.write_text(json.dumps(results, indent=1), encoding="utf-8")

    md = summarise(results)
    (RESULTS / "summary.md").write_text(md, encoding="utf-8")
    png = chart(results, RESULTS / "comparison.png")

    print("\n" + md.split("## Per posting")[0])
    print(f"wrote {raw_path.name}, summary.md" + (", comparison.png" if png else ""))


if __name__ == "__main__":
    main()
