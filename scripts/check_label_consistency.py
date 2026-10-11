"""
Detect self-contradictions in a hand-labelled sheet.

WHY
---
Annotating 310 messages by hand is monotonous and the labelling task genuinely
has a fuzzy boundary (marketing vs fraud). The dangerous failure is not a
blank cell -- it is a template that was labelled correctly 6 times and then
wrong on the 7th, because the annotator's attention drifted.

That kind of error is invisible to a coverage check and to Cohen's kappa,
because both treat each row as independent. But it is also the error most
likely to be duplicated by annotator B (same template, same instinct), so
kappa would report strong agreement on a flawed gold set.

This groups rows by their text with digits masked, so every slot fill of the
same template collapses into one group, then reports any group carrying more
than one label.

Usage:
    python scripts/check_label_consistency.py --sheet data/processed/final_test_blinded_excel.csv
"""
import argparse
import csv
import pathlib
import re
import sys
from collections import Counter, defaultdict

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
VALID = {"legitimate", "marketing_spam", "scam"}


def skeleton(t):
    """Mask digits and collapse whitespace so every slot fill of one template
    maps to the same key."""
    t = re.sub(r"\d[\d,\.]*", "#", t or "")
    t = re.sub(r"[₹$€£]", "#", t)
    return " ".join(t.lower().split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet",
                    default=str(ROOT / "data/processed/final_test_blinded_excel.csv"))
    ap.add_argument("--show", type=int, default=25)
    args = ap.parse_args()

    rows = list(csv.DictReader(
        pathlib.Path(args.sheet).open(encoding="utf-8-sig", newline="")))
    print(f"sheet: {pathlib.Path(args.sheet).name}   rows={len(rows)}\n")

    # ---- 1. label vocabulary ---------------------------------------------
    dist = Counter((r.get("final_label") or "").strip() for r in rows)
    print("LABEL VOCABULARY")
    for k, v in dist.most_common():
        ok = "ok" if k.lower() in VALID else "NOT A VALID CLASS"
        print(f"  {k!r:20} {v:>4}   {ok}")
    bad = [r for r in rows if (r.get("final_label") or "").strip().lower() not in VALID]
    if bad:
        print(f"\n  {len(bad)} rows carry a label outside {sorted(VALID)}.")
        print("  These must be resolved before any score is computed.")

    # ---- 2. template-level self-contradiction ------------------------------
    groups = defaultdict(list)
    for r in rows:
        groups[skeleton(r["text"])].append(r)

    conflicting = []
    for skel, rs in groups.items():
        labs = {(r.get("final_label") or "").strip().lower() for r in rs}
        labs.discard("")
        if len(labs) > 1:
            conflicting.append((skel, rs, labs))

    multi = {k: v for k, v in groups.items() if len(v) > 1}
    n_multi_rows = sum(len(v) for v in multi.values())

    print("\nTEMPLATE GROUPS")
    print(f"  {len(groups)} distinct templates across {len(rows)} rows")
    print(f"  {len(multi)} templates appear more than once ({n_multi_rows} rows)")
    print(f"  {len(conflicting)} of those carry CONFLICTING labels")
    if not conflicting:
        print("\n  no template is labelled two different ways.")

    # ---- 2b. coarser grouping --------------------------------------------
    # The full-text skeleton splits what a human calls one template whenever a
    # slot carries an entity name: "UPI payment of Rs # to SHOPPING MART" and
    # "... to FOOD DELIVERY" are two skeletons but one pattern. Grouping on a
    # fixed-width prefix of the skeleton catches that, at the cost of sometimes
    # merging two genuinely different messages. Over-merging is the safe
    # direction for a consistency check: it produces false alarms to dismiss,
    # not missed contradictions.
    print(f"\n{'='*78}")
    print("COARSER PASS  (first 55 chars of the skeleton)")
    print(f"{'='*78}")
    coarse = defaultdict(list)
    for r in rows:
        coarse[skeleton(r["text"])[:55]].append(r)

    c_multi = {k: v for k, v in coarse.items() if len(v) > 1}
    print(f"  {len(c_multi)} groups of 2+ rows  "
          f"({sum(len(v) for v in c_multi.values())} rows involved)")

    c_conf = []
    for skel, rs in c_multi.items():
        labs = {(r.get("final_label") or "").strip().lower() for r in rs}
        labs.discard("")
        if len(labs) > 1:
            c_conf.append((skel, rs))
    c_conf.sort(key=lambda x: -len(x[1]))

    print(f"  {len(c_conf)} carry conflicting labels\n")

    for skel, rs in c_conf[:args.show]:
        c = Counter((r.get("final_label") or "").strip().lower() for r in rs)
        majority = c.most_common(1)[0][0]
        print(f"  group x{len(rs)}  labels={dict(c)}   majority={majority}")
        print(f"    key: {skel}")
        for r in rs:
            lab = (r.get("final_label") or "").strip().lower()
            mark = "  " if lab == majority else "  <-- differs"
            print(f"      {mark} {r['sample_id']}  {lab:16} {r['text'][:62]}")
        print()

    if c_conf:
        print(f"{'='*78}")
        print(f"SUMMARY: {len(c_conf)} coarser groups are internally inconsistent.")
        print("Resolve these BEFORE a second annotator starts, or annotator B will")
        print("independently repeat the same inconsistency and kappa will report")
        print("strong agreement on a flawed gold set.")
        return 1

    print("  PASS: no coarser group is labelled two different ways.")
    return 0


if __name__ == "__main__":
    sys.exit(main())