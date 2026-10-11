"""
Group the VALIDATION false-scam errors so they can be hand-reviewed.

Safe to iterate on: these rows come from split_val.csv, which is now the
iteration surface. split_test.csv is contaminated (all four models were scored
on it during the comparison) and must not be used to guide changes.

Produces:
  - counts by language x source x template
  - the phrases that actually drive the errors, measured against ALL
    legitimate validation rows so a phrase that is merely common is not
    mistaken for a culprit
  - a hand-review sheet with one row per distinct error pattern
"""
import csv
import pathlib
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
CLASSES = ["legitimate", "marketing_spam", "scam"]

# Devanagari / Telugu tokens are whole words, so a Latin-only word regex misses
# every non-English error. Tokenise on script boundaries too.
WORD_RE = re.compile(r"[a-z0-9']+")
NON_LATIN_TOKEN = re.compile(r"[ऀ-ॿ]+|[ఀ-౿]+")


def tokens(text):
    t = (text or "").lower()
    out = set(WORD_RE.findall(t))
    out |= set(NON_LATIN_TOKEN.findall(t))
    return out


def ngrams(text, nmax=3):
    ws = [w for w in WORD_RE.findall((text or "").lower())]
    g = set()
    for n in range(1, nmax + 1):
        for i in range(len(ws) - n + 1):
            g.add(" ".join(ws[i:i + n]))
    g |= tokens(text)
    return g


def main():
    val = list(csv.DictReader((P / "split_val.csv").open(encoding="utf-8-sig", newline="")))
    fp = list(csv.DictReader((P / "val_false_scam_review.csv").open(encoding="utf-8-sig", newline="")))
    # restrict to the baseline model's errors (model 1) so one model's failure
    # modes are analysed, not the union of four
    fp1 = [r for r in fp if r["model"] == "1_word+char_LR"]
    err_texts = {r["text"] for r in fp1}

    print("=" * 78)
    print(f"VALIDATION FALSE-SCAM ERRORS (model 1_word+char_LR): {len(fp1):,}")
    print("=" * 78)

    print("\nby language:")
    for k, v in Counter(r["language"] for r in fp1).most_common():
        tot = sum(1 for r in val if r["language"] == k)
        leg = sum(1 for r in val if r["language"] == k and r["target_label"] == "legitimate")
        print(f"  {k:12} {v:>4,}  of {leg:,} legit val rows ({v/max(leg,1)*100:5.1f}%)"
              f"   [lang total {tot:,}]")

    print("\nby source:")
    for k, v in Counter(r["source"] for r in fp1).most_common():
        print(f"  {k:22} {v:>4,}")

    print("\nby template_id:")
    for k, v in Counter(r["template_id"] or "(none: real data)" for r in fp1).most_common(14):
        print(f"  {k:26} {v:>4,}")

    print("\nreal vs synthetic:")
    for k, v in Counter(r["real_or_synthetic"] for r in fp1).most_common():
        print(f"  {k:12} {v:>4,}")

    # ---- culprit phrases -------------------------------------------------
    # For each phrase, look at ALL legitimate validation rows containing it and
    # count how many the model misread. A phrase is a real culprit only if it
    # is frequent AND has a high miss rate.
    legit_val = [r for r in val if r["target_label"] == "legitimate"]
    phrase_total = Counter()
    phrase_miss = Counter()
    for r in legit_val:
        g = ngrams(r["text"])
        for p in g:
            phrase_total[p] += 1
            if r["text"] in err_texts:
                phrase_miss[p] += 1

    STOP = set("""a an the is are was were be been being to of in on at for and or
    with your you our us it this that he she they we my me i have has had do does did
    not no yes will would can could please msg sms""".split())

    culprits = []
    for p, n in phrase_total.items():
        if n < 10 or len(p) < 3:
            continue
        if WORD_RE.fullmatch(p) and p in STOP:
            continue
        rate = phrase_miss[p] / n
        if rate >= 0.5:
            culprits.append((n, phrase_miss[p], rate, p))
    culprits.sort(reverse=True)

    print("\n" + "=" * 78)
    print("CULPRIT PHRASES  (present in >=10 legit val rows, >=50% misread as scam)")
    print("=" * 78)
    print(f"{'in legit':>9} {'missed':>7} {'rate':>7}  phrase")
    for n, m, rate, p in culprits[:28]:
        print(f"{n:>9,} {m:>7,} {rate*100:>6.0f}%  {p}")

    # ---- hand-review sheet, one row per distinct pattern ------------------
    seen = set()
    sheet = []
    for r in sorted(fp1, key=lambda x: (x["language"], x["source"], x["text"])):
        key = (r["language"], r["source"], r["template_id"])
        if key in seen:
            continue
        seen.add(key)
        g = ngrams(r["text"])
        top = [p for p, n, m, rate in culprits if p in g]
        sheet.append({
            "language": r["language"],
            "source": r["source"],
            "template_id": r["template_id"],
            "real_or_synthetic": r["real_or_synthetic"],
            "errors_in_group": fp1 and sum(
                1 for x in fp1 if (x["language"], x["source"], x["template_id"]) == key),
            "example_text": r["text"],
            "suspect_phrases": " | ".join(top[:6]),
            "verdict": "",
            "add_as_hard_negative": "",
            "notes": "",
        })

    out = P / "hard_negative_review_sheet.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(sheet[0].keys()))
        w.writeheader()
        w.writerows(sheet)
    print(f"\nwrote {out}  ({len(sheet)} distinct patterns to hand-review)")
    print(f"total distinct error rows: {len(err_texts):,}")


if __name__ == "__main__":
    main()