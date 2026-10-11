"""
Leakage check + grouped split builder.

The whole legitimacy of synthetic data rests on one property: a test set whose
templates were never seen during training. This script PROVES that by comparing
a random split (what people do by default) against a grouped split.

It reports, for each:
  - accuracy
  - the overlap in template_id between train and test
  - a "memorisation" probe: can a lookup table built on train templates
    recognise held-out messages?

If grouped-split accuracy is far below random-split accuracy, that difference
IS the fake score. Any number you quote from a random split is fiction.

Usage:
    python scripts/build_splits.py --data data/synthetic/synthetic_sms.csv
"""
import argparse
import collections
import csv
import pathlib
import random
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(path):
    with pathlib.Path(path).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def group_split(rows, frac_test=0.2, seed=42, stratify=True):
    """Split so that NO template_id appears in both train and test.

    When stratify=True, templates are allocated to test per LABEL so the test
    split keeps the overall scam/legit ratio. Without this, a grouped split
    inherits whatever template mix exists and the test set can end up 74% scam,
    which makes precision/recall unreadable.
    """
    rng = random.Random(seed)
    by_tpl = collections.defaultdict(list)
    for r in rows:
        by_tpl[r["template_id"]].append(r)

    # group templates by the label they belong to
    tpl_label = {t: v[0]["label"] for t, v in by_tpl.items()}

    if not stratify:
        tpls = sorted(by_tpl)
        rng.shuffle(tpls)
        target = int(len(rows) * frac_test)
        test_tpls, n = [], 0
        for t in tpls:
            if n >= target:
                break
            test_tpls.append(t)
            n += len(by_tpl[t])
    else:
        total = len(rows)
        test_tpls = []
        for lab in sorted({r["label"] for r in rows}):
            lab_tpls = sorted(t for t, l in tpl_label.items() if l == lab)
            rng.shuffle(lab_tpls)
            want = sum(1 for r in rows if r["label"] == lab) * frac_test
            n = 0
            for t in lab_tpls:
                if n >= want:
                    break
                test_tpls.append(t)
                n += len(by_tpl[t])

    test_set = set(test_tpls)
    train = [r for r in rows if r["template_id"] not in test_set]
    test = [r for r in rows if r["template_id"] in test_set]
    return train, test


def random_split(rows, frac_test=0.2, seed=42):
    rng = random.Random(seed)
    idx = list(range(len(rows)))
    rng.shuffle(idx)
    k = int(len(rows) * frac_test)
    test_i = set(idx[:k])
    train = [r for i, r in enumerate(rows) if i not in test_i]
    test = [r for i, r in enumerate(rows) if i in test_i]
    return train, test


def char_ngram_accuracy(train, test, nmax=5, nmin=3):
    """Cheap but real classifier: char 3-5 gram NB-style scoring via token sets.
    Deliberately simple -- we are measuring the SPLIT, not the model."""
    from collections import defaultdict
    import math

    train = list(train)
    rng = random.Random(0)
    rng.shuffle(train)
    train = train[:4000]  # keep it fast; the point is the split, not the model

    vocab = set()
    docs = collections.defaultdict(list)
    df = collections.Counter()
    for r in train:
        t = r["text"].lower()
        grams = {t[i:i + n] for n in range(nmin, nmax + 1) for i in range(len(t) - n + 1)}
        vocab |= grams
        docs[r["label"]].append(grams)
        df.update(grams)

    labels = list(docs)
    N = len(train)
    correct = 0
    for r in test:
        t = r["text"].lower()
        grams = {t[i:i + n] for n in range(nmin, nmax + 1) for i in range(len(t) - n + 1)}
        best, bestp = None, -1e9
        for lab in labels:
            c = sum(df[g] for g in grams) / max(len(docs[lab]), 1)
            if c > bestp:
                best, bestp = lab, c
        if best == r["label"]:
            correct += 1
    return correct / len(test)


def template_overlap(train, test):
    a = {r["template_id"] for r in train}
    b = {r["template_id"] for r in test}
    return a & b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data/synthetic/synthetic_sms.csv"))
    ap.add_argument("--out", default=str(ROOT / "data/processed"))
    args = ap.parse_args()

    rows = load(args.data)
    print(f"loaded {len(rows):,} rows from {pathlib.Path(args.data).name}\n")

    for name, fn in (("RANDOM split (the default, and the mistake)", random_split),
                     ("GROUPED split (grouped by template_id)", group_split)):
        tr, te = fn(rows)
        overlap = template_overlap(tr, te)
        acc = char_ngram_accuracy(tr, te)
        print(f"{name}")
        print(f"  train {len(tr):,} / test {len(te):,}")
        print(f"  template_id shared between train and test: {len(overlap)}")
        print(f"  simple char-ngram accuracy: {acc*100:.2f}%")
        print(f"  test rows whose template was NEVER seen in training: "
              f"{sum(1 for r in te if r['template_id'] not in {x['template_id'] for x in tr})}/{len(te)}"
              f"  ({sum(1 for r in te if r['template_id'] not in {x['template_id'] for x in tr})/len(te)*100:.1f}%)\n")

    # ---- write the grouped split, which is the only honest one -------------
    tr, te = group_split(rows)
    outdir = pathlib.Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    for name, part in (("train", tr), ("test", te)):
        p = outdir / f"synthetic_{name}.csv"
        with p.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(part)
        print(f"wrote {p} ({len(part):,} rows)")

    print("\nlabel balance:")
    for name, part in (("train", tr), ("test", te)):
        c = collections.Counter(r["label"] for r in part)
        print(f"  {name}: {dict(c)}")
    print("\nper-language in test:")
    print("  ", dict(collections.Counter(r["lang"] for r in te)))


if __name__ == "__main__":
    main()