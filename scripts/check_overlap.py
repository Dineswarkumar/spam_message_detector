"""
Cross-dataset overlap check.

The 'redasers/difraud' dataset card states its SMS slice was built from the UCI
SMS Spam Collection plus the SMS Phishing dataset, de-duplicated. If that is
true, adding Dataset_5971 on top of UCI gives us far fewer new messages than
the row counts suggest. Measure it instead of trusting the card.

Usage:
    python scripts/check_overlap.py <csvA> <textColA> <labelColA> <csvB> <textColB> <labelColB>
"""
import csv
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def norm(t):
    """Aggressive normalization so trivial whitespace/case edits still collide."""
    return " ".join((t or "").lower().split())


def load(path, text_col, label_col, encodings=("utf-8-sig", "latin-1")):
    for enc in encodings:
        try:
            with Path(path).open(encoding=enc, newline="") as fh:
                rows = list(csv.DictReader(fh))
            if rows:
                return rows, enc
        except UnicodeDecodeError:
            continue
    return [], None


def main():
    a_path, a_text, a_label, b_path, b_text, b_label = sys.argv[1:7]
    a, enc_a = load(a_path, a_text, a_label)
    b, enc_b = load(b_path, b_text, b_label)
    print(f"A = {Path(a_path).name}  ({len(a):,} rows, enc={enc_a})")
    print(f"B = {Path(b_path).name}  ({len(b):,} rows, enc={enc_b})\n")

    a_map = {}
    for r in a:
        a_map.setdefault(norm(r.get(a_text)), set()).add((r.get(a_label) or "").strip())
    b_map = {}
    for r in b:
        b_map.setdefault(norm(r.get(b_text)), set()).add((r.get(b_label) or "").strip())

    a_uniq, b_uniq = set(a_map), set(b_map)
    inter = a_uniq & b_uniq
    union = a_uniq | b_uniq

    print(f"A unique: {len(a_uniq):,}")
    print(f"B unique: {len(b_uniq):,}")
    print(f"OVERLAP:  {len(inter):,}")
    print(f"COMBINED UNIQUE (union): {len(union):,}   <-- what you actually train on\n")

    pct = len(inter) / len(b_uniq) * 100 if b_uniq else 0
    print(f"  {pct:.1f}% of B is already in A")
    print(f"  B contributes {len(b_uniq - a_uniq):,} genuinely NEW messages\n")

    # Label agreement on the overlapping texts. Disagreement here means the two
    # datasets use 'spam' with different meanings and cannot be merged blindly.
    agree = disagree = 0
    conflicts = []
    for k in inter:
        la = {x.lower() for x in a_map[k]}
        lb = {x.lower() for x in b_map[k]}
        # crude binary mapping
        def binv(s):
            return "spam" if ("spam" in s or "smishing" in s) else "ham"
        if binv(la) == binv(lb):
            agree += 1
        else:
            disagree += 1
            if len(conflicts) < 12:
                conflicts.append((k[:90], sorted(la), sorted(lb)))

    print(f"LABEL AGREEMENT on overlapping texts: {agree:,} agree / {disagree:,} disagree")
    if conflicts:
        print("\nexamples where they disagree:")
        for t, la, lb in conflicts:
            print(f"  A={la} B={lb}")
            print(f"    {t}")


if __name__ == "__main__":
    main()