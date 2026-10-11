"""
TF-IDF baseline on the three-class corpus, with GROUPED splits.

Pipeline (as specified): TF-IDF word n-grams + char n-grams -> LogisticRegression,
evaluated per language. MuRIL comparison comes after this is sound.

Critical: splits are grouped by dup_group (and template_id for synthetic), never
random per-row. With a row-random split, every synthetic test message comes from a
template the model memorised and the score is fiction.

Reports macro-F1, per-class P/R/F1, a confusion matrix, and per-language accuracy.
Also prints a leakage self-check so the numbers cannot be silently wrong.
"""
import argparse
import csv
import pathlib
import random
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
from sklearn.pipeline import Pipeline, FeatureUnion

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data/processed"

CLASSES = ["legitimate", "marketing_spam", "scam"]


def load(path):
    with pathlib.Path(path).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def group_key(r):
    """Group identity for splitting. Synthetic rows group by template_id;
    everything else by the near-duplicate group id computed in build_corpus."""
    if r.get("real_or_synthetic") == "synthetic" or r.get("template_id"):
        return f"tpl::{r['template_id']}"
    return f"dup::{r.get('dup_group')}"


def grouped_split(rows, frac_test=0.2, seed=42, stratify=True):
    by_group = defaultdict(list)
    for r in rows:
        by_group[group_key(r)].append(r)

    rng = random.Random(seed)
    if stratify:
        test_groups = []
        for lab in CLASSES:
            g = [k for k, v in by_group.items() if v[0]["target_label"] == lab]
            rng.shuffle(g)
            want = sum(1 for r in rows if r["target_label"] == lab) * frac_test
            n = 0
            for k in g:
                if n >= want:
                    break
                test_groups.append(k)
                n += len(by_group[k])
    else:
        g = sorted(by_group)
        rng.shuffle(g)
        target = len(rows) * frac_test
        test_groups, n = [], 0
        for k in g:
            if n >= target:
                break
            test_groups.append(k)
            n += len(by_group[k])

    ts = set(test_groups)
    train = [r for r in rows if group_key(r) not in ts]
    test = [r for r in rows if group_key(r) in ts]
    return train, test


def build_pipeline():
    """Word n-grams catch natural language; char n-grams are what actually carry
    Devanagari/Telugu and romanized registers, where whitespace tokenisation fails."""
    return Pipeline([
        ("features", FeatureUnion([
            ("word", TfidfVectorizer(
                analyzer="word", ngram_range=(1, 2), min_df=2,
                max_features=200_000, sublinear_tf=True,
                strip_accents="unicode", lowercase=True)),
            ("char", TfidfVectorizer(
                analyzer="char_wb", ngram_range=(2, 5), min_df=2,
                max_features=300_000, sublinear_tf=True,
                lowercase=True)),
        ])),
        ("clf", LogisticRegression(
            C=4.0, max_iter=2000, class_weight="balanced",
            n_jobs=-1, random_state=42)),
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(PROCESSED / "corpus_train_ready.csv"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(PROCESSED / "baseline_report.txt"))
    args = ap.parse_args()

    rows = load(args.corpus)
    rows = [r for r in rows if r["target_label"] in CLASSES]
    print(f"corpus: {len(rows):,} rows")
    print("labels:", dict(Counter(r["target_label"] for r in rows)))

    train, test = grouped_split(rows, seed=args.seed)
    print(f"\nGROUPED split: train {len(train):,} / test {len(test):,}")

    # ---- leakage self-check ------------------------------------------------
    trg = {group_key(r) for r in train}
    teg = {group_key(r) for r in test}
    overlap = trg & teg
    print(f"groups shared train<->test: {len(overlap)}  (MUST be 0)")
    print(f"test rows whose group never appeared in train: "
          f"{sum(1 for r in test if group_key(r) not in trg):,}/{len(test):,}")
    if overlap:
        print("!! LEAKAGE DETECTED -- split is invalid")

    # ---- also show what a row-random split would have claimed --------------
    rnd = random.Random(args.seed)
    idx = list(range(len(rows)))
    rnd.shuffle(idx)
    k = int(len(rows) * 0.2)
    ts_idx = set(idx[:k])
    rtr = [r for i, r in enumerate(rows) if i not in ts_idx]
    rte = [r for i, r in enumerate(rows) if i in ts_idx]
    rtr_g = {group_key(r) for r in rtr}
    leaked = sum(1 for r in rte if group_key(r) in rtr_g)
    print(f"\n(for contrast) ROW-RANDOM split would have leaked "
          f"{leaked:,}/{len(rte):,} test rows ({leaked/len(rte)*100:.1f}%) "
          f"whose template/dup-group was in training")

    print("\ntraining model...")
    pipe = build_pipeline()
    pipe.fit([r["text"] for r in train], [r["target_label"] for r in train])

    ytr = [r["target_label"] for r in train]
    yte = [r["target_label"] for r in test]
    pred = pipe.predict([r["text"] for r in test])

    acc = accuracy_score(yte, pred)
    macro = f1_score(yte, pred, average="macro", labels=CLASSES)
    print(f"\n{'='*70}\nTEST SET (grouped split)\n{'='*70}")
    print(f"accuracy : {acc*100:.2f}%")
    print(f"macro-F1 : {macro*100:.2f}%")
    print(f"size     : {len(test):,}")

    print(f"\n{classification_report(yte, pred, labels=CLASSES, digits=4, zero_division=0)}")

    cm = confusion_matrix(yte, pred, labels=CLASSES)
    print("confusion matrix (rows=true, cols=pred)")
    print(" " * 16 + "".join(f"{c[:9]:>11}" for c in CLASSES))
    for i, c in enumerate(CLASSES):
        print(f"  {c:13}" + "".join(f"{v:>11,}" for v in cm[i]))

    # ---- per-language ------------------------------------------------------
    print(f"\n{'='*70}\nPER-LANGUAGE (grouped split)\n{'='*70}")
    by_lang = defaultdict(list)
    for r, p in zip(test, pred):
        by_lang[r["language"]].append((r["target_label"], p))
    print(f"{'language':12} {'n':>6} {'acc%':>7} {'macroF1%':>9}")
    for lang in sorted(by_lang, key=lambda l: -len(by_lang[l])):
        pairs = by_lang[lang]
        yt = [a for a, _ in pairs]
        yp = [b for _, b in pairs]
        a = accuracy_score(yt, yp)
        f = f1_score(yt, yp, average="macro", labels=CLASSES, zero_division=0)
        print(f"  {lang:10} {len(pairs):>6,} {a*100:>7.2f} {f*100:>9.2f}")

    # ---- real vs synthetic -------------------------------------------------
    print(f"\n{'='*70}\nREAL vs SYNTHETIC (test set)\n{'='*70}")
    by_src = defaultdict(list)
    for r, p in zip(test, pred):
        key = "synthetic" if r["real_or_synthetic"] == "synthetic" else "real"
        by_src[key].append((r["target_label"], p))
    for k in ("real", "synthetic"):
        if not by_src[k]:
            continue
        pairs = by_src[k]
        yt = [a for a, _ in pairs]
        yp = [b for _, b in pairs]
        a = accuracy_score(yt, yp)
        print(f"  {k:10} n={len(pairs):>6,}  acc={a*100:6.2f}%")

    # ---- the hard negatives ------------------------------------------------
    print(f"\n{'='*70}\nHARD NEGATIVE CHECK: legitimate rows that look scary\n{'='*70}")
    scary_rx = ("otp|kyc|verify|block|suspend|account|freeze", )
    import re
    rx = re.compile("|".join(scary_rx), re.I)
    hn = [(r, p) for r, p in zip(test, pred)
          if r["target_label"] == "legitimate" and rx.search(r["text"])]
    if hn:
        right = sum(1 for r, p in hn if p == "legitimate")
        print(f"  test legit rows containing scary keywords: {len(hn):,}")
        print(f"  correctly predicted legitimate: {right:,} ({right/len(hn)*100:.1f}%)")
        print(f"  misread as scam: {sum(1 for r,p in hn if p=='scam'):,}")
        print("\n  examples the model got WRONG:")
        for r, p in hn:
            if p != "legitimate":
                print(f"   [{p:14}] {r['text'][:105]}")

    pathlib.Path(args.out).write_text(
        f"corpus={len(rows)} train={len(train)} test={len(test)}\n"
        f"grouped_overlap={len(overlap)}\n"
        f"accuracy={acc:.4f}\nmacro_f1={macro:.4f}\n",
        encoding="utf-8")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()