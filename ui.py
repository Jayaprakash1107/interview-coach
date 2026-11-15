"""Turning the model's markdown into designed components.

The generator returns markdown. Rendering that directly gives a wall of text
in which the citation - the thing that makes this product different from a
chatbot - is just another bullet. So the output is parsed into structured
questions and each one is rendered as a card whose citation carries its own
verification mark.

Parsing is defensive on purpose: if the prompt format drifts, parse_questions
returns nothing and the caller falls back to plain markdown rather than
showing a broken page.
"""

import html
import re

CITE_LABELS = ("Grounded in", "Why this comes up")
STRONG_LABEL = "Strong answer includes"
WEAK_LABEL = "Weak answer sounds like"

# **1. the question text**
_HEAD = re.compile(r"\*\*\s*(\d+)\.\s*(.+?)\*\*", re.DOTALL)


def _field(block, label):
    """Pull '- Label: value' out of a question block."""
    m = re.search(
        rf"^\s*[-*]?\s*{re.escape(label)}\s*:\s*(.+?)(?=\n\s*[-*]\s*\w|\n\s*\n|\Z)",
        block, re.MULTILINE | re.DOTALL,
    )
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _strip_quotes(text):
    return text.strip().strip('"“”').strip()


def parse_questions(markdown_text):
    """[{num, text, cite, cite_label, strong, weak}] - empty if format drifted."""
    heads = list(_HEAD.finditer(markdown_text))
    if not heads:
        return []

    out = []
    for i, h in enumerate(heads):
        start = h.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(markdown_text)
        block = markdown_text[start:end]

        cite, cite_label = "", ""
        for label in CITE_LABELS:
            val = _field(block, label)
            if val:
                cite, cite_label = _strip_quotes(val), label
                break

        out.append({
            "num": h.group(1),
            "text": re.sub(r"\s+", " ", h.group(2)).strip(),
            "cite": cite,
            "cite_label": cite_label,
            "strong": _field(block, STRONG_LABEL),
            "weak": _field(block, WEAK_LABEL),
        })
    return out


def question_card(q, verified=None):
    """One question with its citation apparatus.

    verified: True / False when the citation was checked, None when it was not
    (role mode makes no claim about a posting, so there is nothing to check).
    """
    e = html.escape
    parts = [
        '<div class="ic-q">',
        '<div class="ic-q-head">',
        f'<div class="ic-q-num">{e(q["num"])}</div>',
        f'<div class="ic-q-text">{e(q["text"])}</div>',
        "</div>",
    ]

    if q["cite"]:
        # The mono mark carries the verdict and the quote carries the evidence.
        # An extra sentence saying "found in the posting" stated it twice.
        if verified is True:
            cls, mark = "ok", "in the posting"
        elif verified is False:
            cls, mark = "bad", "not in the posting"
        else:
            cls, mark = "", q["cite_label"].lower()

        parts += [
            f'<div class="ic-cite {cls}">',
            f'<span class="ic-cite-mark">{e(mark)}</span>',
            f'<span class="ic-cite-body">“{e(q["cite"])}”</span>',
            "</div>",
        ]

    if q["strong"] or q["weak"]:
        parts.append('<div class="ic-guide">')
        if q["strong"]:
            parts.append(f'<div><b>A strong answer includes</b> {e(q["strong"])}</div>')
        if q["weak"]:
            parts.append(f'<div><b>A weak one sounds like</b> {e(q["weak"])}</div>')
        parts.append("</div>")

    parts.append("</div>")
    return "".join(parts)


def check_strip(ok, total):
    """The headline verification result."""
    if ok == total:
        return (
            f'<div class="ic-check ok"><span class="n">{ok}/{total}</span>'
            "<span>Every phrase these questions quote was found in the posting "
            "you gave.</span></div>"
        )
    return (
        f'<div class="ic-check bad"><span class="n">{ok}/{total}</span>'
        f"<span>{total - ok} quoted "
        f"{'phrase was' if total - ok == 1 else 'phrases were'} not found in your "
        "posting. Those questions are marked below.</span></div>"
    )


def mode_strip(mode):
    if mode == "posting":
        return (
            '<div class="ic-mode"><b>Reading your posting.</b> Each question '
            "quotes the phrase it came from, and every quote is checked against "
            "your text.</div>"
        )
    return (
        '<div class="ic-mode"><b>Working from the role alone.</b> These are the '
        "questions this kind of job usually attracts. Paste the posting to get "
        "questions tied to it.</div>"
    )


def overall_block(overall, previous=None):
    delta = ""
    if previous is not None:
        d = overall - previous
        cls = "up" if d > 0 else ("down" if d < 0 else "")
        delta = f'<span class="delta {cls}">{d:+.2f} since last time</span>'
    return (
        f'<div class="ic-overall"><span class="v">{overall}</span>'
        f'<span class="of">out of 5</span>{delta}</div>'
    )


def dimension_block(name, score, reason, delta=None):
    e = html.escape
    segs = "".join(f'<i class="{"on" if i < score else ""}"></i>' for i in range(5))
    d = ""
    if delta:
        cls = "up" if delta > 0 else "down"
        d = f'<span class="ic-dim-delta {cls}">{delta:+d}</span>'
    return (
        '<div class="ic-dim">'
        '<div class="ic-dim-top">'
        f'<span class="ic-dim-name">{e(name)}</span>{d}'
        f'<span class="ic-dim-score">{score}/5</span>'
        "</div>"
        f'<div class="ic-bar">{segs}</div>'
        f'<div class="ic-dim-reason">{e(reason)}</div>'
        "</div>"
    )


def rewrite_block(text):
    return (
        '<div class="ic-rewrite"><span class="lab">One change that would help</span>'
        f'<span class="txt">{html.escape(text)}</span></div>'
    )


def answer_panel(label, score, text):
    e = html.escape
    return (
        f'<div class="ic-ans-head">{e(label)}<span class="s">{score}/5</span></div>'
        f'<div class="ic-ans">{e(text)}</div>'
    )


# The mark is inlined rather than loaded as a file: one HTTP request fewer,
# and it inherits the page's colours if they ever change.
MARK = (
    '<svg class="ic-mark" viewBox="11 6 42 46" role="img" aria-label="Groundwork">'
    '<path d="M 30.00 15.00 a 6.00 6.00 0 1 0 -0.1 0.1 '
    'C 22.80 27.90 18.60 33.00 14.70 36.00 L 16.80 39.00 '
    'C 27.00 34.20 31.50 25.80 31.50 20.10 Z" fill="currentColor"/>'
    '<path d="M 47.00 15.00 a 6.00 6.00 0 1 0 -0.1 0.1 '
    'C 39.80 27.90 35.60 33.00 31.70 36.00 L 33.80 39.00 '
    'C 44.00 34.20 48.50 25.80 48.50 20.10 Z" fill="currentColor"/>'
    '<rect class="ic-rule" x="14" y="44" width="36" height="4.5" rx="2.25"/>'
    "</svg>"
)


def wordmark(size="sm"):
    cls = "ic-lockup" + (" ic-lockup-lg" if size == "lg" else "")
    return f'<div class="{cls}">{MARK}<span class="ic-word">Groundwork</span></div>'


def masthead():
    return (
        '<div class="ic-mast">'
        + wordmark()
        + "<p>Questions drawn from the posting in front of you, each one showing "
        "the line it came from.</p>"
        "</div>"
    )


# ======================================================================
# landing page
# ======================================================================

def hero(claim, lead):
    return (
        '<div class="ic-hero">'
        + wordmark("lg")
        + f'<p class="ic-claim">{claim}</p>'
        f'<p class="ic-lead">{lead}</p>'
        "</div>"
    )


def specimen(question, quote, strong):
    """One real question with its citation, shown at display scale.

    The landing page could describe what the tool produces. Showing one
    instead makes the same point without asking anyone to take it on trust.
    """
    e = html.escape
    return (
        '<div class="ic-specimen">'
        '<div class="ic-spec-label">A question it wrote from the posting below</div>'
        f'<div class="ic-spec-q">{e(question)}</div>'
        '<div class="ic-cite ok ic-spec-cite">'
        '<span class="ic-cite-mark">in the posting</span>'
        f'<span class="ic-cite-body">“{e(quote)}”</span>'
        "</div>"
        f'<div class="ic-spec-guide"><b>A strong answer includes</b> {e(strong)}</div>'
        "</div>"
    )


def routing_rows():
    """The one mechanism that is hard to explain in a sentence."""
    rows = [
        ("A full posting",
         "Every question quotes a line from it, and each quote is searched for "
         "in your text before you see it."),
        ("Just a job title",
         "Questions this kind of role usually attracts, labeled plainly as not "
         "specific to any posting."),
    ]
    out = ['<div class="ic-rows">']
    for left, right in rows:
        out.append(
            '<div class="ic-row">'
            f'<div class="ic-row-k">{html.escape(left)}</div>'
            f'<div class="ic-row-v">{html.escape(right)}</div>'
            "</div>"
        )
    out.append("</div>")
    return "".join(out)


def section(heading, body):
    return (
        f'<div class="ic-sec"><h2>{html.escape(heading)}</h2>'
        f"<p>{body}</p></div>"
    )
