"""Check a draft against Andrew's voice (docs/voice/style-guide.md).

Measures the habits that make machine-drafted posts read alike and that Andrew's own
writing doesn't have: one-line paragraphs, sentence fragments, "It's not X. It's Y."
reversals, bullet-heavy argument, stacks of headings, and stock closers. Thresholds
come from his 141 hand-written posts of 400+ words (2004-2024) and from the NYGeoCon
2025 keynote transcript. It reports; it doesn't rewrite.

Usage: python -m scripts.heo.voice_check FILE [FILE ...]      (Markdown, HTML or text)
       python -m scripts.heo.voice_check --strict FILE          exit 1 on any failure
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Phrases that never appear in Andrew's posts but recur in generated drafts.
STOCK = [
    r"\bclosing thought", r"\bkey takeaways?\b", r"\bin conclusion\b", r"\bat the end of the day\b",
    r"\bit'?s worth noting\b", r"\bin today'?s (fast-paced|world)\b",
    r"\bgame[- ]changer\b", r"\bunlock(s|ing)? (the )?(power|potential)\b",
    r"\bthe scarce resource (isn'?t|is not)\b", r"\bhere'?s (the thing|why|how)\b", r"\blet that sink in\b",
    r"\bthis post is (about|my attempt)\b", r"\bin this post,? i\b", r"\bthe real (cost|question|problem) (is|isn'?t)\b",
    r"\bthat'?s it\.", r"\bthat'?s the (tax|point|trick)\.",
]
# "X isn't Y. It's Z." / "Not X. Y." / "It's not X—it's Y"
REVERSAL = re.compile(
    r"(\b(is|isn'?t|is not|are|aren'?t|are not|was|wasn'?t)\b[^.?!\n]{0,60}[.?!]\s+(it|this|that|they)'?s\b)"
    r"|(^\s*not [^.?!\n]{1,60}\.\s+[A-Z])"
    r"|(\bnot (just |only )?[^.,;\n]{1,40}[—–-]{1,2}\s?(it'?s|but)\b)",
    re.I | re.M,
)


@dataclass
class Report:
    path: str
    words: int = 0
    metrics: dict = field(default_factory=dict)
    failures: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def to_text(raw: str, suffix: str) -> tuple[str, list[str]]:
    """Return plain text and its paragraphs. Front matter and code are dropped."""
    raw = re.sub(r"\A---\n.*?\n---\n", "", raw, flags=re.S)
    raw = re.sub(r"```.*?```", " ", raw, flags=re.S)
    if suffix == ".html" or re.search(r"</p>|<br", raw):
        raw = re.sub(r"<(script|style|pre|blockquote)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
        raw = re.sub(r"<h\d[^>]*>(.*?)</h\d>", r"\n## \1\n", raw, flags=re.S | re.I)
        raw = re.sub(r"<li[^>]*>", "\n- ", raw)
        raw = re.sub(r"</p>|<br ?/?>|</li>|</div>", "\n\n", raw)
        raw = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    raw = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", raw)
    paras = [re.sub(r"[ \t]+", " ", p).strip() for p in re.split(r"\n\s*\n", raw)]
    return raw, [p for p in paras if p]


def sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text)
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[\"'“(A-Z])", text) if len(s.split()) >= 1]


def check(path: Path) -> Report:
    text = path.read_text(encoding="utf-8").translate(str.maketrans("’‘“”", "''\"\""))
    raw, paras = to_text(text, path.suffix)
    r = Report(str(path))
    headings = [p for p in paras if p.startswith("#")]
    bullets = [l for p in paras for l in p.split("\n") if re.match(r"\s*([-*•]|\d+[.)])\s", l)]
    prose = [p for p in paras if not p.startswith("#") and not re.match(r"\s*([-*•]|\d+[.)])\s", p)]
    words = sum(len(p.split()) for p in paras if not p.startswith("#"))
    r.words = words
    if words < 150:
        r.notes.append("too short to judge")
        return r
    sents = [s for p in prose for s in sentences(p)]
    lens = [len(s.split()) for s in sents] or [0]
    one_line = [p for p in prose if len(sentences(p)) == 1 and len(p.split()) < 25]
    k = 1000 / words
    m = r.metrics
    m["sentence length (words, mean)"] = round(sum(lens) / len(lens), 1)
    m["fragments (<6 words)"] = f"{sum(l < 6 for l in lens) / len(lens):.0%}"
    m["one-line paragraphs"] = f"{len(one_line) / max(1, len(prose)):.0%}"
    m["bullet lines per 1000 words"] = round(len(bullets) * k, 1)
    m["headings per 1000 words"] = round(len(headings) * k, 1)
    m["'It's not X. It's Y.' reversals"] = len(REVERSAL.findall(raw))
    m["first person (I/my/me) per 1000"] = round(len(re.findall(r"\b(I|my|me|I'm|I've|I'd)\b", raw)) * k, 1)
    m["parenthetical asides per 1000"] = round(raw.count("(") * k, 1)
    m["named people/places/things per 1000"] = round(
        len(re.findall(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b", " ".join(prose))) * k, 1)
    stock = sorted({m_.group(0) for pat in STOCK for m_ in re.finditer(pat, raw, re.I)})

    # Thresholds: comfortably outside Andrew's range, inside the generated drafts'.
    if float(m["sentence length (words, mean)"]) < 14:
        r.failures.append("sentences average under 14 words; his run about 20, mixing long and short")
    if sum(l < 6 for l in lens) / len(lens) > 0.20:
        r.failures.append("more than 20% of sentences are fragments; he uses one now and then, for a punchline")
    if len(one_line) / max(1, len(prose)) > 0.50:
        r.failures.append("more than half the paragraphs are a single short line; he writes paragraphs")
    if len(bullets) * k > 25:
        r.failures.append("argument carried in bullets; he keeps bullets for resources, specs and step lists")
    if len(headings) * k > 10:
        r.failures.append("too many headings for the length; he uses a few short, often playful ones")
    if m["'It's not X. It's Y.' reversals"] > 1:
        r.failures.append("repeated 'It's not X. It's Y.' reversals; tell what happened instead")
    if float(m["first person (I/my/me) per 1000"]) < 3:
        r.notes.append("little first person; most of his posts say where he was and what he did")
    if stock:
        r.failures.append("stock phrases: " + ", ".join(stock))
    tk = re.findall(r"\[TK:[^\]]*\]", raw)
    if tk:
        r.failures.append(f"{len(tk)} [TK: ...] placeholder(s) still to fill in")
    if not re.search(r"\b(19|20)\d\d\b|\b(last|this) (week|year|month|weekend)\b|\b(yesterday|tonight|today)\b", raw, re.I):
        r.notes.append("no time anchor (a year, 'last week'); his posts are usually situated in time")
    return r


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    failed = False
    for f in args.files:
        r = check(f)
        print(f"\n{r.path}  ({r.words} words)")
        for k_, v in r.metrics.items():
            print(f"  {k_:40} {v}")
        for n in r.notes:
            print(f"  note: {n}")
        for x in r.failures:
            print(f"  FAIL: {x}")
        if not r.failures and r.metrics:
            print("  ok: reads within Andrew's range")
        failed |= bool(r.failures)
    return 1 if (failed and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
