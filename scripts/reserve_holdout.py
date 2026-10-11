"""
Reserve the human-labelled final test set against the training corpus.

Why this exists
---------------
`build_final_eval_sets.py` samples the final test set from `review_queue.csv`
and excludes anything already in `corpus_train_ready.csv`. That was correct at
sampling time -- but it is a one-time check against a snapshot. The corpus is
rebuilt every time the labeller rules change, and a rule change can move a row
FROM review INTO trainable. The final test set then silently becomes
contaminated, and nobody notices until a score is quoted.

This was caught for real: widening the OTP demand patterns to accept the Latin
acronym inside Indic text moved three `atharva` scam rows out of review and into
training. They were already sitting in the 310-row blinded sheet.

The rule
--------
The holdout wins. Any corpus row whose text appears in the blinded final test
set is removed from `corpus_train_ready.csv`, permanently, no matter how many
times the corpus is rebuilt. The cost is a few rows of training data. The cost
of not doing it is that every published number is fiction.

Usage:
    python scripts/reserve_holdout.py            # strip + verify
    python scripts/reserve_holdout.py --check    # verify only, change nothing
"""
import argparse
import csv
import pathlib
import shutil
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"
CORPUS = P / "corpus_train_ready.csv"
HOLDOUT = P / "final_test_blinded.csv"


def norm(t):
    return " ".join((t or "").lower().split())


def read(p):
    return list(csv.DictReader(p.open(encoding="utf-8-sig", newline="")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify only, do not modify the corpus")
    args = ap.parse_args()

    if not HOLDOUT.exists():
        print(f"ERROR: holdout not found: {HOLDOUT}")
        return 1

    holdout = read(HOLDOUT)
    held = {norm(r["text"]) for r in holdout}
    print(f"holdout          : {len(holdout)} rows / {len(held)} distinct texts")

    if not CORPUS.exists():
        print(f"ERROR: corpus not found: {CORPUS}")
        return 1

    rows = read(CORPUS)
    print(f"corpus (before)  : {len(rows)} rows")

    clashes = [r for r in rows if norm(r["text"]) in held]
    print(f"held out of corpus: {len(clashes)} rows")

    if clashes:
        by_src = {}
        for r in clashes:
            by_src[r.get("source", "?")] = by_src.get(r.get("source", "?"), 0) + 1
        for k, v in sorted(by_src.items()):
            print(f"    {k}: {v}")
        for r in clashes[:5]:
            print(f"    - {r['text'][:96]}")

    if not args.check and clashes:
        keep = [r for r in rows if norm(r["text"]) not in held]
        backup = CORPUS.with_name("corpus_train_ready.prereserve.bak")
        shutil.copy2(CORPUS, backup)
        cols = list(rows[0].keys())
        with CORPUS.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(keep)
        print(f"corpus (after)   : {len(keep)} rows")
        print(f"backup           : {backup.name}")

    # ---- verify ----------------------------------------------------------
    rows2 = read(CORPUS)
    still = [r for r in rows2 if norm(r["text"]) in held]
    print()
    if still:
        print(f"FAIL: {len(still)} holdout texts still inside corpus_train_ready.csv")
        return 1
    print("PASS: zero overlap between the blinded final test set and the "
          "training corpus.")
    print("      The final test set remains unseen by every model.")
    return 0


if __name__ == "__main__":
    sys.exit(main())