"""
Create a BLINDED human-annotation copy of data/annotation_sample_150.csv.

Design constraints (must be respected exactly):
  * Does NOT modify or overwrite the source sample, any dataset, the corpus, the
    trained model, or the baseline report. Read-only on everything else.
  * Blinded sheet has exactly four columns:
        review_id, text, human_label, human_reason
    human_label and human_reason are BLANK.
  * No original_label / target_label / label_reason / source / source_id /
    language / script / real_or_synthetic / template_id leaks into the sheet.
  * The join mapping lives in a SEPARATE answer-key file that annotators must
    never receive.
  * No labelling is performed here. The answer key carries only the pre-existing
    metadata needed to reconcile human labels against machine labels later.

Usage:
    python scripts/make_blinded_annotation.py
"""
import csv
import hashlib
import pathlib
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "data/annotation_sample_150.csv"
BLINDED = ROOT / "data/annotation_blinded_145.csv"
ANSWERKEY = ROOT / "data/annotation_answer_key_145.csv"

# Columns allowed in the blinded sheet.
BLIND_COLS = ["review_id", "text", "human_label", "human_reason"]

# Columns that must never appear in the blinded sheet.
FORBIDDEN = [
    "original_label", "target_label", "label_reason", "source", "source_id",
    "language", "script", "real_or_synthetic", "template_id",
    "template_or_source_id", "notes", "dup_group", "category",
]


def review_id(text, index):
    """Stable, deterministic, content-addressed ID.

    Derived from the text so that regenerating the sheet produces identical IDs,
    and distinct for identical texts appearing twice in the sample (the index
    suffix disambiguates those cases deterministically by position).
    """
    h = hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:10]
    return f"R{index:03d}-{h}"


def main():
    if not SRC.exists():
        print(f"ERROR: source sample not found: {SRC}")
        sys.exit(1)

    # Refuse to clobber existing annotation artefacts.
    for p in (BLINDED, ANSWERKEY):
        if p.exists():
            print(f"ERROR: refusing to overwrite existing file: {p}")
            sys.exit(1)

    with SRC.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    print(f"source sample: {SRC.name}  rows={len(rows)}")
    print(f"source columns: {list(rows[0].keys())}")

    ids = [review_id(r["text"], i) for i, r in enumerate(rows)]
    if len(set(ids)) != len(ids):
        print("ERROR: review_id collision; aborting")
        sys.exit(1)

    # ---- blinded sheet: exactly four columns -------------------------------
    with BLINDED.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(BLIND_COLS)
        for rid, r in zip(ids, rows):
            w.writerow([rid, r["text"], "", ""])

    # ---- answer key: NOT for annotators ------------------------------------
    key_cols = ["review_id", "sample_row_number", "text",
                "original_label", "target_label", "label_reason", "source",
                "source_id", "template_id", "category", "language", "script",
                "real_or_synthetic"]
    with ANSWERKEY.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=key_cols, extrasaction="ignore")
        w.writeheader()
        for i, (rid, r) in enumerate(zip(ids, rows), start=2):
            # sample_row_number = line number in the ORIGINAL sample csv
            # (1-based including header), so any row can be recovered exactly.
            w.writerow({
                "review_id": rid,
                "sample_row_number": i,
                "text": r["text"],
                "original_label": r.get("original_label", ""),
                "target_label": r.get("target_label", ""),
                "label_reason": r.get("label_reason", ""),
                "source": r.get("source", ""),
                "source_id": r.get("source_id", ""),
                "template_id": r.get("template_id", ""),
                "category": r.get("category", ""),
                "language": r.get("language", ""),
                "script": r.get("script", ""),
                "real_or_synthetic": r.get("real_or_synthetic", ""),
            })

    print(f"\nwrote {BLINDED}  ({len(rows)} rows)")
    print(f"wrote {ANSWERKEY}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()