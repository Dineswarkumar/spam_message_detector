"""
Report class x SCRIPT coverage, and per-language x script cross-tab.

Why script and not language
---------------------------
Almost every real Indian scam message is code-mixed: Devanagari body with Latin
"OTP", "KYC", "UPI", or a latin URL embedded. Our language tag therefore files
those rows under hinglish/tenglish, and the pure-native buckets look tiny
(hindi 86, telugu 49) even though Devanagari/Telugu script coverage is large.

Script is also what the char-ngram vectorizer actually observes, so it is the
honest axis for a performance claim. Language is kept as a secondary tag.
"""
import csv
import pathlib
import sys
from collections import Counter, defaultdict

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLASSES = ["legitimate", "marketing_spam", "scam"]


def main():
    p = ROOT / "data/processed/corpus_train_ready.csv"
    with p.open(encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["target_label"] in CLASSES]

    print(f"trainable rows: {len(rows):,}\n")

    print("=" * 74)
    print("CLASS x SCRIPT  (the axis the vectorizer sees)")
    print("=" * 74)
    tab = defaultdict(Counter)
    for r in rows:
        tab[r["script"]][r["target_label"]] += 1
    print(f"{'script':18} {'legit':>8} {'mkt_spam':>9} {'scam':>8} {'total':>8}")
    for s in sorted(tab, key=lambda s: -sum(tab[s].values())):
        c = tab[s]
        print(f"  {s:16} {c.get('legitimate',0):>8,} {c.get('marketing_spam',0):>9,} "
              f"{c.get('scam',0):>8,} {sum(c.values()):>8,}")

    print("\n" + "=" * 74)
    print("LANGUAGE x SCRIPT cross-tab")
    print("=" * 74)
    x = Counter((r["language"], r["script"]) for r in rows)
    for (lg, sc), n in x.most_common(14):
        print(f"  {lg:12} -> {sc:24} {n:>7,}")

    print("\n" + "=" * 74)
    print("ADEQUACY BY SCRIPT  (>=500 per class to support a claim)")
    print("=" * 74)
    for s in sorted(tab, key=lambda s: -sum(tab[s].values())):
        c = tab[s]
        thin = [k for k in CLASSES if c.get(k, 0) < 500]
        flag = "OK " if not thin else "!! "
        print(f"  {flag}{s:18} total {sum(c.values()):>7,}   thin: {thin or 'none'}")

    print("\n" + "=" * 74)
    print("REAL vs SYNTHETIC by script (how much is human-written?)")
    print("=" * 74)
    rs = defaultdict(Counter)
    for r in rows:
        rs[r["script"]][r["real_or_synthetic"]] += 1
    for s in sorted(rs, key=lambda s: -sum(rs[s].values())):
        c = rs[s]
        tot = sum(c.values())
        print(f"  {s:18} real {c.get('real',0):>6,} ({c.get('real',0)/tot*100:5.1f}%)  "
              f"synthetic {c.get('synthetic',0):>6,} ({c.get('synthetic',0)/tot*100:5.1f}%)")

    print("\n" + "=" * 74)
    print("DEVANAGARI / TELUGU script: real vs synthetic split per class")
    print("=" * 74)
    for sc in ("devanagari", "telugu"):
        sub = [r for r in rows if r["script"] == sc]
        if not sub:
            print(f"  {sc}: none")
            continue
        cc = Counter((r["target_label"], r["real_or_synthetic"]) for r in sub)
        print(f"  {sc} ({len(sub):,} rows):")
        for lab in CLASSES:
            rr = cc.get((lab, "real"), 0)
            ss = cc.get((lab, "synthetic"), 0)
            print(f"      {lab:15} real {rr:>5,}  synthetic {ss:>6,}")


if __name__ == "__main__":
    main()