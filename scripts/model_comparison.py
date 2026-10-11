"""
Four-model comparison on one fixed three-way grouped split.

    train  65%   -- fitting only
    val    17.5% -- ALL model selection, error analysis, hard-negative review
    test   17.5% -- touched ONCE at the end, for the final number only

Why this restructure
--------------------
train_baseline.py used a two-way train/test split, so the 89 false-scam
hard-negative errors that were inspected for failure-mode analysis came FROM
THE TEST SET. Any iteration driven by those errors would make the test score
optimistic. The split is now three-way and the test slice is written to disk
and left alone until the final report.

Models compared (identical features/split, only the vectoriser/classifier varies):
    1. word+char TF-IDF -> LogisticRegression   (current baseline)
    2. word-only TF-IDF -> LogisticRegression   (ablation)
    3. char-only TF-IDF -> LogisticRegression   (ablation)
    4. word+char TF-IDF -> LinearSVC            (classifier swap)

Usage:
    python scripts/model_comparison.py
"""
import csv
import json
import pathlib
import random
import re
import sys
from collections import Counter, defaultdict

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score)
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

ROOT = pathlib.Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"
CLASSES = ["legitimate", "marketing_spam", "scam"]
SEED = 42

WORD = dict(analyzer="word", ngram_range=(1, 2), min_df=2,
            max_features=200_000, sublinear_tf=True,
            strip_accents="unicode", lowercase=True)
CHAR = dict(analyzer="char_wb", ngram_range=(2, 5), min_df=2,
            max_features=300_000, sublinear_tf=True, lowercase=True)


def group_key(r):
    if r.get("real_or_synthetic") == "synthetic" or r.get("template_id"):
        return f"tpl::{r['template_id']}"
    return f"dup::{r.get('dup_group')}"


def from_pretrained(vectorizers):
    """Build a Pipeline that concatenates several vectorised feature blocks."""
    from sklearn.pipeline import FeatureUnion
    feats = FeatureUnion(vectorizers)
    return feats


def build_models():
    from sklearn.pipeline import FeatureUnion
    return {
        "1_word+char_LR": Pipeline([
            ("f", FeatureUnion([("w", TfidfVectorizer(**WORD)),
                                ("c", TfidfVectorizer(**CHAR))])),
            ("clf", LogisticRegression(C=4.0, max_iter=2000,
                                       class_weight="balanced", random_state=SEED)),
        ]),
        "2_word_only_LR": Pipeline([
            ("f", FeatureUnion([("w", TfidfVectorizer(**WORD))])),
            ("clf", LogisticRegression(C=4.0, max_iter=2000,
                                       class_weight="balanced", random_state=SEED)),
        ]),
        "3_char_only_LR": Pipeline([
            ("f", FeatureUnion([("c", TfidfVectorizer(**CHAR))])),
            ("clf", LogisticRegression(C=4.0, max_iter=2000,
                                       class_weight="balanced", random_state=SEED)),
        ]),
        "4_word+char_SVC": Pipeline([
            ("f", FeatureUnion([("w", TfidfVectorizer(**WORD)),
                                ("c", TfidfVectorizer(**CHAR))])),
            ("clf", LinearSVC(C=0.5, class_weight="balanced", random_state=SEED)),
        ]),
    }


def three_way_grouped_split(rows, val_frac=0.175, test_frac=0.175, seed=SEED):
    """Grouped on template_id/dup_group, stratified by label. No group appears
    in more than one slice -- asserted before returning."""
    rng = random.Random(seed)
    by_group = defaultdict(list)
    for r in rows:
        by_group[group_key(r)].append(r)

    val_groups, test_groups = set(), set()
    for lab in CLASSES:
        groups = sorted(k for k, v in by_group.items() if v[0]["target_label"] == lab)
        rng.shuffle(groups)
        n_val = int(len(groups) * val_frac)
        val_groups.update(groups[:n_val])
        test_groups.update(groups[n_val:n_val + int(len(groups) * test_frac)])

    train = [r for r in rows if group_key(r) not in val_groups and group_key(r) not in test_groups]
    val = [r for r in rows if group_key(r) in val_groups]
    test = [r for r in rows if group_key(r) in test_groups]
    return train, val, test


SCARY = re.compile(r"otp|kyc|verify|block|suspend|account|freeze|restrict|"
                   r"pending|expire|ओटीपी|केवाईसी|ఓటీపీ|కెవైసీ", re.I)


def evaluate(model, split, name):
    Xtr = [r["text"] for r in split["train"]]
    ytr = [r["target_label"] for r in split["train"]]
    Xev = [r["text"] for r in split[name]]
    yev = [r["target_label"] for r in split[name]]
    model.fit(Xtr, ytr)
    pred = model.predict(Xev)
    acc = accuracy_score(yev, pred)
    macro = f1_score(yev, pred, average="macro", labels=CLASSES, zero_division=0)
    rep = classification_report(yev, pred, labels=CLASSES, output_dict=True,
                                zero_division=0)
    return model, pred, acc, macro, rep


def slice_report(pred, split, label):
    """Per-language accuracy + hard-negative rate on one slice."""
    print(f"  {'language':12} {'n':>6} {'acc%':>7}")
    by_lang = defaultdict(list)
    for r, p in zip(split, pred):
        by_lang[r["language"]].append((r["target_label"], p))
    for lg in sorted(by_lang, key=lambda l: -len(by_lang[l])):
        pairs = by_lang[lg]
        yt = [a for a, _ in pairs]
        yp = [b for _, b in pairs]
        print(f"    {lg:10} {len(pairs):>6,} {accuracy_score(yt, yp)*100:>7.2f}")

    hn = [(r, p) for r, p in zip(split, pred)
          if r["target_label"] == "legitimate" and SCARY.search(r["text"])]
    if hn:
        wrong = sum(1 for r, p in hn if p == "scam")
        print(f"    hard negatives: {len(hn):,}  misread as scam: {wrong:,} "
              f"({wrong/len(hn)*100:.1f}%)")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-only", action="store_true",
                    help="skip the test slice entirely (default while the "
                         "review queue is still unlabelled)")
    cli = ap.parse_args()

    rows = list(csv.DictReader(
        (P / "corpus_train_ready.csv").open(encoding="utf-8-sig", newline="")))
    rows = [r for r in rows if r["target_label"] in CLASSES]
    print(f"corpus: {len(rows):,} rows  {dict(Counter(r['target_label'] for r in rows))}")

    train, val, test = three_way_grouped_split(rows)
    split = {"train": train, "val": val, "test": test}

    # ---- leakage assertions ---------------------------------------------
    gtr = {group_key(r) for r in train}
    gva = {group_key(r) for r in val}
    gte = {group_key(r) for r in test}
    print(f"\nsplit: train {len(train):,} / val {len(val):,} / test {len(test):,}")
    print(f"  groups train&val  : {len(gtr & gva)}  (must be 0)")
    print(f"  groups train&test : {len(gtr & gte)}  (must be 0)")
    print(f"  groups val&test   : {len(gva & gte)}  (must be 0)")
    assert not (gtr & gva) and not (gtr & gte) and not (gva & gte), "LEAKAGE"

    for nm in ("val", "test"):
        print(f"  {nm}: {dict(Counter(r['target_label'] for r in split[nm]))}")

    # persist the fixed split so every later run reuses it
    cols = list(rows[0].keys())
    for nm in ("train", "val", "test"):
        fp = P / f"split_{nm}.csv"
        with fp.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(split[nm])
        print(f"  wrote {fp.name}")

    # ---- model comparison, selected on VAL --------------------------------
    results = {}
    for name, model in build_models().items():
        print(f"\n{'='*74}\n{name}\n{'='*74}")
        _, pred, acc, macro, rep = evaluate(model, split, "val")
        results[name] = {"val_acc": acc, "val_macro_f1": macro,
                         "per_class": {c: rep[c] for c in CLASSES}}
        print(f"VAL accuracy {acc*100:.2f}%   macro-F1 {macro*100:.2f}%")
        print(classification_report([r["target_label"] for r in val], pred,
                                    labels=CLASSES, digits=4, zero_division=0))
        cm = confusion_matrix([r["target_label"] for r in val], pred, labels=CLASSES)
        print("confusion (rows=true):")
        for i, c in enumerate(CLASSES):
            print(f"  {c:15}" + "".join(f"{v:>8,}" for v in cm[i]))
        print("  language / hard-negative slices:")
        slice_report(pred, val, "val")

    best = max(results, key=lambda k: results[k]["val_macro_f1"])
    print(f"\n{'='*74}\nBEST ON VALIDATION: {best} "
          f"(macro-F1 {results[best]['val_macro_f1']*100:.2f}%)\n{'='*74}")

    # ---- TEST, evaluated once, only now -----------------------------------
    if cli.val_only:
        print(f"\n{'='*74}\nTEST SLICE SKIPPED (--val-only).")
        print("split_test.csv is contaminated: all four models were scored on it "
              "and\nchar-only was named the test winner, so test performance "
              "influenced selection.\nThe final score will come from "
              "final_test_human_labelled.csv once a human\nlabels the review "
              "queue (data no model has ever seen).\n{'='*74}")
    else:
        print(f"\n{'='*74}\nFINAL TEST SLICE (first and only touch)\n{'='*74}")
        for name, model in build_models().items():
            model.fit([r["text"] for r in train], [r["target_label"] for r in train])
            pred = model.predict([r["text"] for r in test])
            yt = [r["target_label"] for r in test]
            acc = accuracy_score(yt, pred)
            macro = f1_score(yt, pred, average="macro", labels=CLASSES, zero_division=0)
            results[name]["test_acc"] = acc
            results[name]["test_macro_f1"] = macro
            star = " *" if name == best else "  "
            print(f"{star}{name:20} test acc {acc*100:6.2f}%   macro-F1 {macro*100:6.2f}%")

        model = build_models()[best]
        model.fit([r["text"] for r in train], [r["target_label"] for r in train])
        pred = model.predict([r["text"] for r in test])
        print(f"\nper-class detail on TEST for {best}:")
        print(classification_report([r["target_label"] for r in test], pred,
                                    labels=CLASSES, digits=4, zero_division=0))
        print("  language / hard-negative slices:")
        slice_report(pred, test, "test")

    (P / "model_comparison.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {P/'model_comparison.json'}")

    # ---- dump VALIDATION false positives for human review -----------------
    fp_rows = []
    for nm, m in build_models().items():
        m.fit([r["text"] for r in train], [r["target_label"] for r in train])
        pv = m.predict([r["text"] for r in val])
        for r, p in zip(val, pv):
            if p == "scam" and r["target_label"] == "legitimate":
                fp_rows.append({"model": nm, "text": r["text"],
                                "language": r["language"], "script": r["script"],
                                "source": r["source"],
                                "template_id": r["template_id"] or "",
                                "real_or_synthetic": r["real_or_synthetic"]})
    outp = P / "val_false_scam_review.csv"
    with outp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fp_rows[0].keys()))
        w.writeheader()
        w.writerows(fp_rows)
    print(f"wrote {outp} ({len(fp_rows)} rows, all from VALIDATION -- safe to iterate on)")


if __name__ == "__main__":
    main()