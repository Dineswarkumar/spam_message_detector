"""
Measure per-script coverage across every REAL source (not synthetic).

Answers precisely: which languages do we actually have real text for, and how
much? Distinguishes Telugu (Telugu script) from Tanglish (Telugu written in
Roman/Latin letters), which is a separate language register entirely.

Usage:
    python scripts/language_coverage.py
"""
import csv
import importlib.util
import json
import pathlib
import re
import sys
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]

RANGES = {
    "devanagari": (0x0900, 0x097F),
    "bengali": (0x0980, 0x09FF),
    "telugu": (0x0C00, 0x0C7F),
    "tamil": (0x0B80, 0x0BFF),
    "kannada": (0x0C80, 0x0CFF),
    "malayalam": (0x0D00, 0x0D7F),
    "gujarati": (0x0A80, 0x0AFF),
    "gurmukhi": (0x0A00, 0x0A7F),
    "arabic": (0x0600, 0x06FF),
    "latin": (0x0041, 0x024F),
}

# Romanized-Hindi markers vs Romanized-Telugu markers. These are different
# languages that happen to share an alphabet -- which is exactly why char n-grams
# need both, and why "Hinglish" coverage cannot stand in for "Tanglish".
HINGLISH = {
    "aap", "aapka", "aapki", "aapke", "hai", "hain", "karo", "kare", "karein",
    "karna", "kripya", "turant", "abhi", "bilkul", "nahi", "nhi", "mat", "sir",
    "madam", "khatam", "bhejo", "khul", "block", "dena", "dunga", "dungi",
    "waqt", "jaldi", "pakka", "dhyan", "shukriya", "namaste", "accha", "paisa",
    "rupaye", "kripya",
}
TANGLISH = {
    "nuvvu", "meeku", "meeku", "garu", "kavali", "undi", "undi", "chalundi",
    "pettu", "petta", "aapavu", "raaledu", "raaledu", "nenu", "meeku", "em",
    "iki", "kurchi", "vachayi", "theeyali", "theeyali", "saledu", "paisalu",
    "cheppali", "cheppu", "vanki", "vandi", "manchi", "sundari", "dhanyaludu",
    "krupya", "kaani", "aaputha", "band", "block", "surakshalu",
}


def scripts_of(text):
    s = set()
    for ch in text:
        cp = ord(ch)
        for name, (lo, hi) in RANGES.items():
            if lo <= cp <= hi:
                s.add(name)
    return s


def register_of(text):
    """Classify a Latin-script message as english / hinglish / tanglish / unknown."""
    words = set(re.findall(r"[a-z']+", text.lower()))
    if len(words & TANGLISH) >= 2:
        return "tanglish"
    if len(words & HINGLISH) >= 2:
        return "hinglish"
    return "english/unknown"


def dedup(texts):
    return list({" ".join(t.lower().split()) for t in texts if t and t.strip()})


def main():
    sources = {}

    # UCI
    p = ROOT / "dataset/01_uci_sms_spam/SMSSpamCollection"
    if p.exists():
        texts = []
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if "\t" in line:
                texts.append(line.split("\t", 1)[1])
        sources["UCI SMS Spam"] = texts

    # legacy multilingual
    p = ROOT / "dataset/02_legacy_old_repo_rakshasutra/multilingual_fraud_dataset.csv"
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as fh:
            sources["legacy multilingual"] = [r["text"] for r in csv.DictReader(fh)]

    # legacy merged dataset (mostly UCI, includes the above)
    p = ROOT / "dataset/02_legacy_old_repo_rakshasutra/dataset.csv"
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as fh:
            sources["legacy merged"] = [r["text"] for r in csv.DictReader(fh)]

    # ysangam
    p = ROOT / "dataset/03_needs_verification/ysangam_india_cyber_scam.csv"
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as fh:
            sources["ysangam 10k"] = [r["text"] for r in csv.DictReader(fh)]

    # karanverma
    p = ROOT / "dataset/03_needs_verification/karanverma19_ultra_premium_scam.csv"
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as fh:
            sources["karanverma19"] = [r["message"] for r in csv.DictReader(fh)]

    # phishing 5971
    p = ROOT / "dataset/SMS PHISHING DATASET FOR MACHINE LEARNING AND PATTERN RECOGNITION/Dataset_5971.csv"
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as fh:
            sources["Dataset_5971"] = [r["TEXT"] for r in csv.DictReader(fh)]

    # atharva taxonomy
    p = ROOT / "dataset/04_phishing_taxonomy_atharva/atharva_dataset.py"
    if p.exists():
        spec = importlib.util.spec_from_file_location("ath", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        allm = list(getattr(mod, "PHISHING_MESSAGES", [])) + \
               list(getattr(mod, "LEGIT_MESSAGES", []))
        sources["atharva taxonomy"] = [
            x.get("message", "") if isinstance(x, dict) else str(x) for x in allm]

    # crowdsourced Indian dataset (Yadav et al. 2011, IIIT Delhi)
    p = ROOT / "dataset/-SMS-Spam-Classification-on-Indian-Dataset-A-Crowdsourced-Collection-of-Hindi-and-English-Messages-main/indian_spam.csv"
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as fh:
            sources["INDIAN crowdsourced 2011"] = [r["v2"] for r in csv.DictReader(fh)]

    # synthetic (clearly marked, for comparison)
    p = ROOT / "data/synthetic/synthetic_sms.csv"
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as fh:
            sources["SYNTHETIC (generated)"] = [r["text"] for r in csv.DictReader(fh)]

    print("=" * 78)
    print("REAL-SOURCE SCRIPT COVERAGE (deduplicated, by Unicode script)")
    print("=" * 78)

    totals = Counter()
    per_source = {}
    for name, texts in sources.items():
        u = dedup(texts)
        c = Counter()
        for t in u:
            for s in scripts_of(t):
                c[s] += 1
        per_source[name] = (len(u), c)
        if "SYNTHETIC" not in name:
            totals.update(c)

    for name, (n, c) in per_source.items():
        marker = "  " if "SYNTHETIC" not in name else "* "
        print(f"\n{marker}{name}  ({n:,} unique)")
        for s, k in c.most_common():
            print(f"      {s:12} {k:>6,}  ({k/n*100:5.1f}%)")

    print("\n" + "=" * 78)
    print("COMBINED REAL TOTAL (all real sources pooled, deduped)")
    print("=" * 78)
    print(f"  devanagari (Hindi)  {totals.get('devanagari',0):>6,}")
    print(f"  telugu   (Telugu)   {totals.get('telugu',0):>6,}")
    print(f"  latin               {totals.get('latin',0):>6,}")

    # Romanized register breakdown on latin-only real messages
    print("\n" + "=" * 78)
    print("LATIN-SCRIPT MESSAGES, SPLIT BY LANGUAGE REGISTER")
    print("=" * 78)
    reg_all = Counter()
    per_src_reg = {}
    for name, texts in sources.items():
        if "SYNTHETIC" in name:
            continue
        u = dedup(texts)
        r = Counter()
        for t in u:
            if "latin" in scripts_of(t) and "devanagari" not in scripts_of(t) \
               and "telugu" not in scripts_of(t):
                r[register_of(t)] += 1
        per_src_reg[name] = r
        reg_all.update(r)

    for name, r in per_src_reg.items():
        if sum(r.values()):
            print(f"\n  {name}")
            for k, v in r.most_common():
                print(f"      {k:16} {v:>6,}")
    print("\n  === COMBINED REAL ===")
    for k, v in reg_all.most_common():
        print(f"      {k:16} {v:>6,}")

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    te = totals.get("telugu", 0)
    de = totals.get("devanagari", 0)
    tang = reg_all.get("tanglish", 0)
    hing = reg_all.get("hinglish", 0)
    print(f"  Telugu script (real)      : {te:,}")
    print(f"  Tanglish  (real)          : {tang:,}")
    print(f"  Devanagari (real)         : {de:,}")
    print(f"  Hinglish  (real)          : {hing:,}")
    if te == 0:
        print("\n  !! ZERO real Telugu. Any Telugu support is synthetic-only.")
    if tang == 0:
        print("  !! ZERO real Tanglish. Romanized Telugu is entirely uncovered,")
        print("     and cannot be substituted by Hinglish -- different language,")
        print("     different romanization conventions (retroflex consonants,")
        print("     'nuvvu/meeku' vs 'aap/aapka', aspirated vs unaspirated).")


if __name__ == "__main__":
    main()
