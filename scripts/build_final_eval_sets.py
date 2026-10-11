"""
Build the FINAL evaluation sets from data never touched by any model.

Why these two sheets exist
--------------------------
1. `final_test_human_labelled.csv`
   split_test.csv is CONTAMINATED. All four models were scored on it during the
   comparison, and char-only was named the test winner -- so test performance
   influenced model selection. Its numbers are exploratory, not final.

   The only rows never seen by any model are the 1,951 currently sitting in
   `review` state: excluded from corpus_train_ready.csv, so absent from train,
   val AND test. Once a human labels them they become a genuinely pristine test
   set. This script samples them stratified by source / script / auto-label and
   emits a blank labelling sheet.

2. `tenglish_native_review.csv`
   A sample of the Tenglish rows for a fluent speaker to verify BOTH the label
   and whether the text is natural Tenglish at all. Several templates were
   written by an LLM and may read as translated Hindi rather than Tenglish.
   These rows must NOT be used to tune the model -- the point is to audit the
   data, not to fit it.

Neither sheet is used for fitting or tuning. Run, hand to a human, then use
sheet 1 exactly once for the final score.

Usage:
    python scripts/build_final_eval_sets.py --test-sample 400 --tenglish-sample 150
"""
import argparse
import csv
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

ROOT = pathlib.Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"


def norm(t):
    return " ".join((t or "").lower().split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-sample", type=int, default=400)
    ap.add_argument("--tenglish-sample", type=int, default=150)
    ap.add_argument("--seed", type=int, default=101)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    review = list(csv.DictReader((P / "review_queue.csv").open(encoding="utf-8-sig", newline="")))
    used = {norm(r["text"]) for r in
            csv.DictReader((P / "corpus_train_ready.csv").open(encoding="utf-8-sig", newline=""))}

    # ---------- 1. pristine final test set --------------------------------
    pool = [r for r in review if norm(r["text"]) not in used]
    print(f"review queue: {len(review):,}   not present in train/val/test: {len(pool):,}")

    buckets = defaultdict(list)
    for r in pool:
        buckets[(r["source"], r["script"])].append(r)
    keys = sorted(buckets)
    per = max(1, args.test_sample // len(keys))
    sample = []
    for k in keys:
        b = buckets[k][:]
        rng.shuffle(b)
        sample += b[:per]
    rng.shuffle(sample)
    sample = sample[:args.test_sample]

    cols = ["sample_id", "text", "final_label", "annotator", "reason", "notes"]
    out = P / "final_test_human_labelled.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for i, r in enumerate(sample, 1):
            w.writerow({
                "sample_id": f"FT{i:04d}",
                "text": r["text"],
                "final_label": "",        # legitimate | marketing_spam | scam
                "annotator": "",
                "reason": "",
                "notes": f"auto_guess={r['auto_target_label']}|"
                         f"why_review={r['label_reason']}|src={r['source']}",
            })
    print(f"\nwrote {out}  ({len(sample)} rows)")
    print(f"  stratified by (source, script): {len(keys)} strata, ~{per} each")
    for k in keys[:12]:
        print(f"    {k[0]:22} {k[1]:22} pool {len(buckets[k]):>5,}")

    # ---------- 2. Tenglish native-speaker audit ---------------------------
    corpus = list(csv.DictReader((P / "corpus_train_ready.csv").open(encoding="utf-8-sig", newline="")))
    te = [r for r in corpus if r["language"] == "tenglish"]
    # dedup near-identical slot fills so the reviewer sees real variety
    seen, uniq = set(), []
    for r in te:
        k = re.sub(r"\d+", "#", norm(r["text"]))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    sample2 = uniq[:]
    rng.shuffle(sample2)
    sample2 = sample2[:args.tenglish_sample]

    cols2 = ["sample_id", "text", "lang_code", "label_check", "natural_tenglish",
             "translation_quality", "notes"]
    out2 = P / "tenglish_native_review.csv"
    with out2.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols2)
        w.writeheader()
        for i, r in enumerate(sample2, 1):
            w.writerow({
                "sample_id": f"TE{i:04d}",
                "text": r["text"],
                "lang_code": r["language"],
                # label_check: correct | wrong | unsure
                "label_check": "",
                # natural_tenglish: yes | partly (reads translated) | no (not Tenglish)
                "natural_tenglish": "",
                "translation_quality": "",
                "notes": f"auto_label={r['target_label']}|template={r['template_id']}|"
                         f"real_or_syn={r['real_or_synthetic']}",
            })
    print(f"\nwrote {out2}  ({len(sample2)} rows)")
    print(f"  tenglish pool {len(te):,} -> {len(uniq):,} after collapsing slot repeats")
    print(f"  by label: {dict(Counter(r['target_label'] for r in uniq))}")
    print(f"  real vs synthetic: {dict(Counter(r['real_or_synthetic'] for r in uniq))}")


if __name__ == "__main__":
    main()