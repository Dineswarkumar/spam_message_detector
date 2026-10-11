"""
Produce a properly BLINDED annotator copy of the final test set, plus a separate
answer key.

Why this exists
---------------
`final_test_human_labelled.csv` was built with an auto-populated `notes` column
containing `auto_guess=...`, `why_review=...` and `src=...`. Anyone labelling
while reading that column is anchored on the regex labeller's output, which is
exactly what an independently human-labelled test set must NOT be.

So:
  final_test_blinded.csv   -- what the annotator actually sees
  final_test_answer_key.csv -- join back to sample_id, kept by the project owner

Blinded columns: sample_id, text, final_label (blank), reason (blank).
Nothing else. Verified programmatically below.

Usage:
    python scripts/blind_final_test_set.py
"""
import csv
import pathlib
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"
SRC = P / "final_test_human_labelled.csv"
BLIND = P / "final_test_blinded.csv"
KEY = P / "final_test_answer_key.csv"

VALID = {"legitimate", "marketing_spam", "scam"}

# Anything that could hint at provenance, source or the machine label.
FORBIDDEN_TOKENS = [
    "auto_guess", "why_review", "src=", "source", "script", "template",
    "real_or_synthetic", "original_label", "target_label", "label_reason",
    "uci", "atharva", "synthetic", "ysangam", "indian2011", "phishing5971",
    "legacy_ml", "indian_spam", "spam.csv",
]


def main():
    rows = list(csv.DictReader(SRC.open(encoding="utf-8-sig", newline="")))
    print(f"source: {SRC.name}  rows={len(rows)}")

    if BLIND.exists() or KEY.exists():
        print("ERROR: refusing to overwrite an existing blinded sheet / answer key")
        sys.exit(1)

    # ---- blinded sheet ----------------------------------------------------
    cols = ["sample_id", "text", "final_label", "reason"]
    with BLIND.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({"sample_id": r["sample_id"], "text": r["text"],
                        "final_label": "", "reason": ""})

    # ---- answer key -------------------------------------------------------
    with KEY.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["sample_id", "text", "auto_guess",
                                           "why_review", "source", "script",
                                           "language", "real_or_synthetic",
                                           "template_id"])
        w.writeheader()
        for r in rows:
            note = r["notes"]
            def field(k, default=""):
                for part in note.split("|"):
                    if part.startswith(k + "="):
                        return part[len(k) + 1:]
                return default
            w.writerow({
                "sample_id": r["sample_id"], "text": r["text"],
                "auto_guess": field("auto_guess"),
                "why_review": field("why_review"),
                "source": field("src"),
                "script": "", "language": "", "real_or_synthetic": "",
                "template_id": "",
            })

    # ---- verify no leak ---------------------------------------------------
    blind_rows = list(csv.DictReader(BLIND.open(encoding="utf-8-sig", newline="")))
    assert list(blind_rows[0].keys()) == cols, blind_rows[0].keys()
    leaks = []
    for r in blind_rows:
        blob = " ".join(r.values()).lower()
        for tok in FORBIDDEN_TOKENS:
            if tok.lower() in blob:
                leaks.append((r["sample_id"], tok))
    print(f"\nblinded sheet : {BLIND.name}  ({len(blind_rows)} rows)")
    print(f"  columns      : {cols}")
    print(f"  all labels blank: "
          f"{all(not r['final_label'].strip() for r in blind_rows)}")
    print(f"  leak check   : {'CLEAN' if not leaks else leaks[:10]}")
    print(f"answer key    : {KEY.name}  (keep away from annotators)")

    if leaks:
        print("\nERROR: metadata leaked into the blinded sheet")
        sys.exit(1)


if __name__ == "__main__":
    main()