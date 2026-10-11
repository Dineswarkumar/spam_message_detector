"""
Validate the hand-labelled final test set, and score agreement between two
independent annotators.

Usage:
    python scripts/validate_final_labels.py                      # coverage check
    python scripts/validate_final_labels.py --a A.csv --b B.csv # agreement
    python scripts/validate_final_labels.py --merge              # build merged set

Rules enforced:
  * final_label must be one of legitimate / marketing_spam / scam
  * every row labelled, no blanks
  * if two annotators are supplied, report raw agreement AND Cohen's kappa,
    and list every disagreement for resolution
  * sanity warnings: one annotator defaulting to a single class, or a label
    distribution wildly unlike the corpus (usually means guessing)

It does NOT decide anything. It reports.
"""
import argparse
import csv
import pathlib
import sys
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"
VALID = ["legitimate", "marketing_spam", "scam"]


def load(p):
    return {r["sample_id"]: r for r in
            csv.DictReader(pathlib.Path(p).open(encoding="utf-8-sig", newline=""))}


def cohen_kappa(a, b, labels=VALID):
    n = len(a)
    if n == 0:
        return 0.0
    obs = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    exp = sum((ca[l] / n) * (cb[l] / n) for l in labels)
    return (obs - exp) / (1 - exp) if exp < 1 else 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default=str(P / "final_test_blinded.csv"))
    ap.add_argument("--a", help="annotator A sheet")
    ap.add_argument("--b", help="annotator B sheet")
    ap.add_argument("--merge", action="store_true",
                    help="write the agreed final test set")
    ap.add_argument("--out", default=str(P / "FINAL_TEST_SET.csv"))
    cli = ap.parse_args()

    # ---------------- single-annotator coverage --------------------------
    rows = list(csv.DictReader(pathlib.Path(cli.sheet).open(encoding="utf-8-sig", newline="")))
    print(f"sheet: {pathlib.Path(cli.sheet).name}  rows={len(rows)}")
    filled = [r for r in rows if r["final_label"].strip()]
    print(f"labelled: {len(filled)}/{len(rows)}  ({len(filled)/len(rows)*100:.1f}%)")

    bad = [r for r in filled if r["final_label"].strip().lower() not in VALID]
    if bad:
        print(f"\n!! {len(bad)} rows have an invalid label. Allowed: {VALID}")
        for r in bad[:10]:
            print(f"   {r['sample_id']}  {r['final_label']!r}  {r['text'][:70]}")
        return 1
    blank = [r for r in rows if not r["final_label"].strip()]
    if blank:
        print(f"\n{len(blank)} rows still unlabelled:")
        for r in blank[:10]:
            print(f"   {r['sample_id']}  {r['text'][:70]}")
        if len(blank) > 10:
            print(f"   ... and {len(blank)-10} more")
        print("\nFill these in before the final score is computed.")

    dist = Counter(r["final_label"].strip().lower() for r in filled)
    print("\nlabel distribution:")
    for k in VALID:
        n = dist.get(k, 0)
        pct = n / len(filled) * 100 if filled else 0
        bar = "#" * int(pct / 2)
        print(f"  {k:16} {n:>4,}  ({pct:5.1f}%) {bar}")

    if len(set(dist.values())) == 1 and len(filled) > 30:
        print("\n!! every class has the same count -- suspicious, check for guessing")

    # ---------------- two-annotator agreement ----------------------------
    if cli.a and cli.b:
        A, B = load(cli.a), load(cli.b)
        common = sorted(set(A) & set(B))
        print(f"\n{'='*66}\nAGREEMENT\n{'='*66}")
        print(f"  annotator A rows: {len(A)}   B rows: {len(B)}   common ids: {len(common)}")
        if not common:
            print("  no common sample_id values")
            return 1
        a = [A[i]["final_label"].strip().lower() for i in common]
        b = [B[i]["final_label"].strip().lower() for i in common]
        unlabelled = sum(1 for x, y in zip(a, b) if not x or not y)
        if unlabelled:
            print(f"  !! {unlabelled} rows not labelled by BOTH -- resolve those first")
        agree = sum(1 for x, y in zip(a, b) if x == y)
        print(f"  raw agreement : {agree}/{len(common)} = {agree/len(common)*100:.2f}%")
        k = cohen_kappa(a, b)
        print(f"  Cohen's kappa : {k:.4f}")
        if k < 0.6:
            print("  kappa < 0.60  -> labels are not reliable enough to report")
        elif k < 0.8:
            print("  kappa < 0.80  -> usable, but document the disagreements")
        else:
            print("  kappa >= 0.80 -> strong agreement")

        print("\n  per-class agreement:")
        for lab in VALID:
            ta = sum(1 for x in a if x == lab)
            tb = sum(1 for y in b if y == lab)
            both = sum(1 for x, y in zip(a, b) if x == lab and y == lab)
            print(f"    {lab:16} A={ta:>4}  B={tb:>4}  both={both:>4}")

        dis = [(i, A[i]["final_label"], B[i]["final_label"], A[i]["text"])
               for i in common
               if A[i]["final_label"].strip().lower() != B[i]["final_label"].strip().lower()]
        print(f"\n  {len(dis)} disagreements to resolve:")
        for i, la, lb, txt in dis[:40]:
            print(f"    {i}  A={la:15} B={lb:15} {txt[:60]}")
        if len(dis) > 40:
            print(f"    ... and {len(dis)-40} more")

        if cli.merge:
            if dis:
                print("\nrefusing to merge while disagreements remain")
                return 1
            with open(cli.out, "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=["sample_id", "text",
                                                   "final_label", "reason"])
                w.writeheader()
                for i in common:
                    w.writerow({"sample_id": i, "text": A[i]["text"],
                                "final_label": a[common.index(i)],
                                "reason": A[i].get("reason", "")})
            print(f"\nwrote {cli.out} ({len(common)} rows, unanimous)")
    return 0


if __name__ == "__main__":
    sys.exit(main())