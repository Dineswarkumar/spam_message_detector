"""
Rewrite the CSV annotation sheets with a UTF-8 BOM so Excel opens them correctly.

Problem
-------
`final_test_blinded.csv` was valid UTF-8 but had no byte-order mark. Excel on
Windows guesses the encoding for a BOM-less CSV and falls back to cp1252, which
renders Devanagari/Telugu as mojibake (â‚¤à‚¤...). The data was never corrupt --
only Excel's decoder was wrong. A BOM makes Excel auto-detect UTF-8.

Writes to NEW filenames rather than overwriting, because Excel holds a lock on
any open workbook. Output goes to `*_excel.csv`.

Usage:
    python scripts/fix_csv_for_excel.py
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
FILES = ["final_test_blinded.csv", "final_test_answer_key.csv",
         "tenglish_native_review.csv", "final_test_disagreements.csv"]


def rewrite(path: pathlib.Path):
    out = path.with_name(path.stem + "_excel.csv")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        rows = list(reader)
    if not rows:
        print(f"  skip {path.name}: empty")
        return None
    # utf-8-sig writes the BOM; csv handles quoting/embedded commas/newlines
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        csv.writer(fh).writerows(rows)
    raw = out.read_bytes()
    has_bom = raw[:3] == b"\xef\xbb\xbf"
    # confirm it still decodes strictly as UTF-8 after the BOM
    text = raw.decode("utf-8-sig")
    return out, has_bom, len(rows) - 1, len(text)


def main():
    for name in FILES:
        src = P / name
        if not src.exists():
            print(f"  missing: {name}")
            continue
        res = rewrite(src)
        if not res:
            continue
        out, has_bom, nrows, nchars = res
        print(f"  {name}")
        print(f"    -> {out.name}   rows={nrows:,}  chars={nchars:,}  "
              f"BOM={'yes' if has_bom else 'NO'}  decodes as UTF-8: OK")
    print("\nOpen the *_excel.csv versions in Excel.")


if __name__ == "__main__":
    main()