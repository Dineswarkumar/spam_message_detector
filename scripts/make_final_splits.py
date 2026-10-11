"""
Write the canonical train/val slices that backend/train.py fits on.

WHY THIS EXISTS
---------------
`backend/train.py` reads split_train.csv / split_val.csv, but nothing in the
pipeline regenerated them. They were leftovers from the v1 corpus. Fitting on
stale slices means the shipped artifact is trained on a corpus that no longer
exists, and its validation number describes a model nobody can reproduce.

This script is the single place the shipped split is defined. It reuses the
exact grouping and seed from scripts/model_comparison.py so the number
reported here is the same one model selection was done on. If the two ever
disagree, the comparison script's number is the honest one and this file is
buggy.

It also refuses to run if any row of the human-labelled holdout has leaked into
the corpus. See scripts/reserve_holdout.py.

Usage:
    python scripts/make_final_splits.py
"""
import csv
import importlib.util
import pathlib
import sys
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mc = load("mc", ROOT / "scripts/model_comparison.py")


def norm(t):
    return " ".join((t or "").lower().split())


def write(path, rows):
    cols = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path.name}  ({len(rows):,} rows)")


def main():
    rows = list(csv.DictReader(
        (P / "corpus_train_ready.csv").open(encoding="utf-8-sig", newline="")))
    rows = [r for r in rows if r["target_label"] in mc.CLASSES]
    print(f"corpus: {len(rows):,} rows  {dict(Counter(r['target_label'] for r in rows))}")

    holdout = P / "final_test_blinded.csv"
    if holdout.exists():
        held = {norm(r["text"]) for r in csv.DictReader(
            holdout.open(encoding="utf-8-sig", newline=""))}
        leaked = sum(1 for r in rows if norm(r["text"]) in held)
        if leaked:
            print(f"\nABORT: {leaked} holdout rows are inside the corpus.")
            print("Run: python scripts/reserve_holdout.py")
            return 1
        print(f"holdout reservation: PASS ({len(held)} distinct texts, 0 in corpus)")

    train, val, test = mc.three_way_grouped_split(rows)
    gtr = {mc.group_key(r) for r in train}
    gva = {mc.group_key(r) for r in val}
    gte = {mc.group_key(r) for r in test}
    assert not (gtr & gva) and not (gtr & gte) and not (gva & gte), "GROUP LEAKAGE"

    print(f"\nsplit: train {len(train):,} / val {len(val):,} / held-back test {len(test):,}")
    print(f"  groups train&val {len(gtr & gva)}   train&test {len(gtr & gte)}   "
          f"val&test {len(gva & gte)}   (all must be 0)")

    write(P / "split_train.csv", train)
    write(P / "split_val.csv", val)
    # The test slice stays written out but is NOT scored by anything. It was
    # already contaminated once (all four models were scored on it and char-only
    # was declared the winner), so it cannot be un-contaminated. The pristine
    # test set is the hand-labelled holdout.
    write(P / "split_test.csv", test)

    print("\nNOTE: split_test.csv is kept for provenance only. Do not score on it --")
    print("      it is contaminated by the original model comparison. The honest")
    print("      final number comes from the hand-labelled holdout.")
    return 0


if __name__ == "__main__":
    sys.exit(main())