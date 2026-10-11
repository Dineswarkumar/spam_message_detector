"""
Diff v1 vs v2 corpus labels, grouped by template_id.

Purpose: verify the rule fix and the new non-Latin fraud patterns did what was
intended and nothing else. Any template whose label distribution moved is a
candidate regression -- especially legit -> scam on a HARD NEGATIVE template,
which is the exact failure mode the hard negatives exist to catch.
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
P = ROOT / "data/processed"


def norm(t):
    return " ".join((t or "").lower().split())


def load(p):
    d = {}
    for r in csv.DictReader(p.open(encoding="utf-8-sig", newline="")):
        d.setdefault(norm(r["text"]), r)
    return d


def main():
    v1 = load(P / "v1_corpus_labeled.csv")
    v2 = load(P / "corpus_labeled.csv")

    by_tpl = defaultdict(lambda: (Counter(), Counter()))
    for k, r1 in v1.items():
        r2 = v2.get(k)
        if not r2:
            continue
        t = r2.get("template_id") or f"[{r2['source']}]"
        by_tpl[t][0][r1["target_label"]] += 1
        by_tpl[t][1][r2["target_label"]] += 1

    print("=" * 78)
    print("TEMPLATES WHOSE LABEL DISTRIBUTION CHANGED (v1 -> v2)")
    print("=" * 78)
    moved = []
    for t in sorted(by_tpl):
        a, b = by_tpl[t]
        if a != b:
            moved.append((t, a, b))

    for t, a, b in moved:
        print(f"\n  {t}")
        print(f"    v1: {dict(a)}")
        print(f"    v2: {dict(b)}")

    print(f"\n{len(moved)} templates changed")

    # ---- specifically: any legit -> scam movement? ------------------------
    print("\n" + "=" * 78)
    print("REGRESSION CHECK: legit -> scam (hard negatives must NOT flip)")
    print("=" * 78)
    regressions = []
    for t in sorted(by_tpl):
        a, b = by_tpl[t]
        flip = sum(min(a[k], b[k]) for k in a)  # rough overlap
        gained = b["scam"] - a["scam"]
        if gained > 0:
            regressions.append((t, a, b, gained))
    for t, a, b, g in regressions:
        print(f"  {t}: scam {a['scam']} -> {b['scam']}  (+{g})   legit {a['legitimate']} -> {b['legitimate']}")

    print("\n" + "=" * 78)
    print("SAMPLE MESSAGES FROM TEMPLATES THAT FLIPPED (legit -> scam)")
    print("=" * 78)
    shown = 0
    for k, r1 in v1.items():
        r2 = v2.get(k)
        if not r2:
            continue
        if r1["target_label"] == "legitimate" and r2["target_label"] == "scam":
            t = r2.get("template_id") or f"[{r2['source']}]"
            print(f"\n  {t}")
            print(f"    {r2['text'][:150]}")
            shown += 1
            if shown >= 12:
                break
    if not shown:
        print("  (none)")


if __name__ == "__main__":
    main()