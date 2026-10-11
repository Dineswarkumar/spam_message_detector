"""
Audit a candidate spam/scam dataset before we trust it.

Usage:
    python scripts/audit_dataset.py data/raw/legacy_old_repo/multilingual_fraud_dataset.csv

Answers the questions that decide whether the dataset is usable:
  - how many rows, and how are labels distributed?
  - what languages actually appear (script detection, not self-reported metadata)?
  - is it real text or template filler?
  - how many duplicates?
"""
import csv
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

# The Windows console defaults to cp1252 and will crash on Devanagari/Telugu.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# Unicode ranges for the scripts we care about, not metadata claims.
SCRIPT_RANGES = {
    "devanagari": (0x0900, 0x097F),  # Hindi, Marathi, Nepali
    "bengali": (0x0980, 0x09FF),
    "telugu": (0x0C00, 0x0C7F),
    "tamil": (0x0B80, 0x0BFF),
    "kannada": (0x0C80, 0x0CFF),
    "malayalam": (0x0D00, 0x0D7F),
    "gujarati": (0x0A80, 0x0AFF),
    "punjabi/gurmukhi": (0x0A00, 0x0A7F),
    "arabic/urdu": (0x0600, 0x06FF),
    "latin": (0x0041, 0x024F),
    "cyrillic": (0x0400, 0x04FF),
}

# Common Romanized-Hindi (Hinglish) function words. Presence of 2+ of these in a
# latin-script message is the standard cheap signal that it is not plain English.
HINGLISH_MARKERS = {
    "aap", "aapka", "aapki", "aapke", "hai", "hain", "karo", "kare", "karein",
    "karna", "kripya", "turant", "abhi", "bilkul", "nhi", "nahi", "mat",
    "sir", "madam", "sms", "rupaye", "paisa", "khatam", "bhejo", "bhej",
    "khul", "band", "block", "kar", "dena", "dunga", "dungi", "waqt",
    "jaldi", "pakka", "bharosa", "dhyan", "shukriya", "namaste", "accha",
}

MOJIBAKE_MARKERS = ["Ã©", "Ã¨", "Ã¢", "Ã¤", "à¤", "à°", "à¥", "â‚¹", "â€", "Ã¢", "Â "]


def read_rows(path: Path):
    """Read a CSV, tolerating encoding damage. Returns list of dicts."""
    last_err = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with path.open(encoding=enc, newline="") as fh:
                rows = list(csv.DictReader(fh))
            return rows, enc
        except UnicodeDecodeError as e:
            last_err = e
        except Exception as e:  # malformed csv etc.
            last_err = e
    print(f"  !! could not read as text: {last_err}")
    return [], None


def pick_text_label(rows):
    """Find the message column and the label column without hardcoding names."""
    if not rows:
        return None, None
    keys = list(rows[0].keys())
    label_col = next(
        (k for k in keys if k and k.strip().lower() in
         {"label", "class", "v1", "type", "category", "target", "is_spam", "spam"}),
        None,
    )
    text_col = next(
        (k for k in keys if k and k.strip().lower() in
         {"text", "message", "sms", "v2", "content", "body", "msg"}),
        None,
    )
    if label_col is None and len(keys) >= 2:
        label_col = keys[0]
    if text_col is None and len(keys) >= 2:
        text_col = keys[1]
    return text_col, label_col


def detect_scripts(text: str):
    found = set()
    for ch in text:
        cp = ord(ch)
        for name, (lo, hi) in SCRIPT_RANGES.items():
            if lo <= cp <= hi:
                found.add(name)
    return found


def repair_mojibake(text: str) -> str:
    """Undo UTF-8 bytes that were decoded as latin-1/cp1252."""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/audit_dataset.py <csv> [more.csv ...]")
        sys.exit(1)

    for arg in sys.argv[1:]:
        path = Path(arg)
        print("=" * 70)
        print(f"FILE: {path.name}")
        if not path.exists():
            print("  MISSING\n")
            continue
        print(f"  size: {path.stat().st_size:,} bytes")

        rows, enc = read_rows(path)
        print(f"  encoding used: {enc}")
        print(f"  rows: {len(rows):,}")
        if not rows:
            print("  no rows parsed\n")
            continue

        text_col, label_col = pick_text_label(rows)
        print(f"  columns: {list(rows[0].keys())}")
        print(f"  using text='{text_col}' label='{label_col}'")

        texts = [(r.get(text_col) or "") for r in rows]
        labels = [(r.get(label_col) or "") for r in rows]

        # --- label distribution -------------------------------------------------
        lc = Counter(l.strip() for l in labels)
        print(f"\n  LABEL DISTRIBUTION ({len(lc)} distinct):")
        for lab, n in lc.most_common(10):
            print(f"    {lab!r:24} {n:>7,}  ({n/len(rows)*100:5.1f}%)")

        # --- empty / missing ----------------------------------------------------
        empties = sum(1 for t in texts if not t.strip())
        print(f"\n  empty messages: {empties:,}")

        # --- encoding damage ----------------------------------------------------
        damaged = 0
        for t in texts[:2000]:
            if any(m in t for m in MOJIBAKE_MARKERS):
                damaged += 1
        print(f"  mojibake in first 2000 rows: {damaged}")

        # --- script distribution ------------------------------------------------
        print("\n  LANGUAGE (measured, not self-reported):")
        script_counts = Counter()
        hinglish_count = 0
        latin_only = 0
        for t in texts:
            s = detect_scripts(t)
            for name in s:
                script_counts[name] += 1
            if "latin" in s:
                latin_only += 1
                words = set(re.findall(r"[a-z]+", t.lower()))
                if len(words & HINGLISH_MARKERS) >= 2:
                    hinglish_count += 1
        for name, n in script_counts.most_common():
            print(f"    {name:16} {n:>7,}  ({n/len(texts)*100:5.1f}%)")
        print(f"    {'~ Hinglish':16} {hinglish_count:>7,}  "
              f"({hinglish_count/len(texts)*100:5.1f}%)  [2+ Hinglish markers]")

        # --- duplicates ---------------------------------------------------------
        norm = [" ".join(t.lower().split()) for t in texts]
        uniq = len(set(norm))
        dupes = len(texts) - uniq
        print(f"\n  DUPLICATES: {dupes:,} ({dupes/len(texts)*100:.1f}%)"
              f"  -> {uniq:,} unique")

        # --- template-filler heuristic -----------------------------------------
        # Synthetic data repeats boilerplate. Count the most common word and the
        # most common trailing 12-char slice across messages.
        word_c = Counter()
        for t in norm:
            word_c.update(re.findall(r"[\w']+", t))
        tail_c = Counter(t[-12:] for t in norm if len(t) >= 12)
        print(f"\n  TEMPLATE CHECK:")
        if word_c:
            w, n = word_c.most_common(1)[0]
            print(f"    most common word: {w!r} in {n} rows ({n/len(texts)*100:.1f}%)")
        if tail_c:
            tl, tn = tail_c.most_common(1)[0]
            print(f"    most common ending: {tl!r} in {tn} rows ({tn/len(texts)*100:.1f}%)")

        # --- length -------------------------------------------------------------
        lens = sorted(len(t) for t in texts)
        if lens:
            print(f"\n  LENGTH chars: min={lens[0]} p50={lens[len(lens)//2]} "
                  f"p95={lens[int(len(lens)*0.95)]} max={lens[-1]}")

        # --- samples ------------------------------------------------------------
        print("\n  SAMPLES:")
        for i in range(min(4, len(rows))):
            t = texts[i]
            if damaged and any(m in t for m in MOJIBAKE_MARKERS):
                t = repair_mojibake(t)
            shown = t[:150].replace("\n", " ")
            print(f"    [{labels[i]}] {shown}")
        print()


if __name__ == "__main__":
    main()