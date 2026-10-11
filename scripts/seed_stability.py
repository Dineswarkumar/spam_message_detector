"""
Seed-stability check for the model choice.

WHY THIS EXISTS
---------------
After adding the legitimate hard-negative templates, the validation numbers
moved enough to change the shipping decision: word+char SVC used to miss 2% of
hard negatives against word+char LR's 26%, and that 24-point gap was the stated
reason for shipping SVC. After the fix every model sits at ~0.5% hard-negative
miss, and char-only LR leads macro-F1 by ~1.4 points.

Picking a shipping model on a single 1.4-point difference from one split is not
defensible. This re-runs the top candidates across several seeds so the choice
rests on a difference that survives resampling.

Val only. The test slice stays sealed.
"""
import csv
import importlib.util
import pathlib
import statistics
import sys
from collections import Counter, defaultdict

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

SEEDS = [42, 7, 2026]
CANDIDATES = ["1_word+char_LR", "3_char_only_LR", "4_word+char_SVC"]


def norm(t):
    return " ".join((t or "").lower().split())


def main():
    rows = list(csv.DictReader(
        (P / "corpus_train_ready.csv").open(encoding="utf-8-sig", newline="")))
    rows = [r for r in rows if r["target_label"] in mc.CLASSES]
    print(f"corpus: {len(rows):,} rows  {dict(Counter(r['target_label'] for r in rows))}")

    held = {norm(r["text"]) for r in csv.DictReader(
        (P / "final_test_blinded.csv").open(encoding="utf-8-sig", newline=""))}
    leaked = sum(1 for r in rows if norm(r["text"]) in held)
    if leaked:
        print(f"ABORT: {leaked} holdout rows are inside the training corpus. "
              "Run scripts/reserve_holdout.py first.")
        return 1
    print("holdout reservation: PASS (0 leaked rows)\n")

    models = mc.build_models()
    results = {c: {"f1": [], "hn": [], "acc": []} for c in CANDIDATES}

    for seed in SEEDS:
        train, val, _t = mc.three_way_grouped_split(rows, seed=seed)
        gtr = {mc.group_key(r) for r in train}
        gva = {mc.group_key(r) for r in val}
        assert not (gtr & gva), "LEAKAGE"
        split = {"train": train, "val": val}
        print(f"--- seed {seed}: train {len(train):,} / val {len(val):,} ---")

        hn_total = [(r, ) for r in val
                    if r["target_label"] == "legitimate" and mc.SCARY.search(r["text"])]

        for cand in CANDIDATES:
            _m, pred, acc, macro, _rep = mc.evaluate(models[cand], split, "val")
            hn = [(r, p) for (r,), p in zip(hn_total, pred)]
            hn_wrong = sum(1 for r, p in hn if p == "scam")
            hn_rate = hn_wrong / len(hn) if hn else 0.0
            results[cand]["f1"].append(macro)
            results[cand]["acc"].append(acc)
            results[cand]["hn"].append(hn_rate)
            print(f"  {cand:18} acc {acc*100:6.2f}%  macro-F1 {macro*100:6.2f}%"
                  f"   hard-neg {hn_wrong:>3}/{len(hn)} ({hn_rate*100:4.2f}%)")
        print()

    print("=" * 76)
    print(f"SEED STABILITY  (mean +/- half-range over {len(SEEDS)} grouped splits,"
          " validation only)")
    print("=" * 76)
    for cand in CANDIDATES:
        f1s = [x * 100 for x in results[cand]["f1"]]
        half = (max(f1s) - min(f1s)) / 2
        print(f"  {cand:18} macro-F1 {statistics.mean(f1s):6.2f}% +/- {half:4.2f}"
              f"   hard-neg miss {statistics.mean(results[cand]['hn'])*100:5.2f}%")

    ranked = sorted(CANDIDATES, key=lambda c: -statistics.mean(results[c]["f1"]))
    top, second = ranked[0], ranked[1]
    gap = (statistics.mean(results[top]["f1"]) - statistics.mean(results[second]["f1"])) * 100
    half_top = (max(results[top]["f1"]) - min(results[top]["f1"])) / 2 * 100

    print()
    print(f"leader: {top}  by {gap:.2f} points over {second}")
    if gap <= half_top:
        print(f"  NOT STABLE: the gap is inside {top}'s own seed spread "
              f"(+/- {half_top:.2f}). Treat as a tie and decide on a different axis.")
    else:
        print(f"  STABLE: the gap exceeds {top}'s seed spread "
              f"(+/- {half_top:.2f}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())