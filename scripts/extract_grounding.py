"""
Extract grounded building blocks from the REAL audited sources.

Synthetic data is only defensible if the slots we fill come from real observed
text, not from our imagination. This script mines:

  - scam categories + the vocabulary that co-occurs with each
  - real entity names (banks, platforms, government bodies)
  - legit transactional patterns (the hard negatives)

Everything downstream references these. Run this before generate_synthetic.py.
"""
import collections
import csv
import importlib.util
import json
import pathlib
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_atharva():
    """Import the taxonomy python module and pull its message lists."""
    p = ROOT / "data/raw/phishing_taxonomy/atharva_dataset.py"
    spec = importlib.util.spec_from_file_location("atharva", p)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        print(f"  could not import atharva_dataset.py: {e}")
        return [], []
    phish = getattr(mod, "PHISHING_MESSAGES", []) or []
    legit = getattr(mod, "LEGIT_MESSAGES", []) or []
    # entries are dicts
    ptxt = [x.get("message", "") if isinstance(x, dict) else str(x) for x in phish]
    ltxt = [x.get("message", "") if isinstance(x, dict) else str(x) for x in legit]
    return [t for t in ptxt if t], [t for t in ltxt if t]


def load_ysangam():
    p = ROOT / "data/raw/needs_verification/ysangam_india_cyber_scam.csv"
    if not p.exists():
        return []
    with p.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    # dedup, keep first occurrence
    seen, out = set(), []
    for r in rows:
        t = (r.get("text") or "").strip()
        k = " ".join(t.lower().split())
        if t and k not in seen:
            seen.add(k)
            out.append({"text": t, "label": r.get("label"),
                        "category": r.get("scam_category"),
                        "urgency": r.get("urgency_level"),
                        "caller": r.get("caller_type")})
    return out


def load_phishing5971():
    p = ROOT / "dataset/SMS PHISHING DATASET FOR MACHINE LEARNING AND PATTERN RECOGNITION/Dataset_5971.csv"
    if not p.exists():
        return []
    with p.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for r in rows:
        t = (r.get("TEXT") or "").strip()
        lab = (r.get("LABEL") or "").strip().lower()
        lab = {"smishing": "scam", "spam": "spam", "ham": "legit"}.get(lab, lab)
        if t:
            out.append({"text": t, "label": lab,
                        "url": r.get("URL", ""), "phone": r.get("PHONE", "")})
    return out


# Entities we have actually SEEN in the audited corpora, grouped by role.
ENTITIES = {
    "bank": ["SBI", "HDFC", "ICICI", "Axis Bank", "Kotak Mahindra", "PNB",
             "Bank of India", "Canara Bank", "Federal Bank", "IDFC First",
             "Yes Bank", "IndusInd", "RBI"],
    "platform": ["Amazon", "Flipkart", "Myntra", "Swiggy", "Zomato", "Ola",
                 "Uber", "PhonePe", "Google", "Facebook", "Instagram",
                 "WhatsApp", "Paytm", "IRCTC", "Ajio", "Nykaa", "Tata CLiQ"],
    "govt": ["UIDAI", "Income Tax Department", "EPFO", "ESIC", "RBI", "SEBI",
             "Election Commission", "NREGA", "MCA", "GSTN", "TRAI", "Police"],
    "telecom": ["Airtel", "Jio", "Vi", "BSNL", "MTNL"],
}

# Urgency / pressure cues measured from real scam samples.
SCAM_PRESSURE = {
    "en": ["urgent", "immediately", "within 24 hours", "right now", "act now",
           "final warning", "last chance", "expires today", "avoid permanent closure",
           "your account will be blocked", "do not ignore this"],
    "hinglish": ["turant", "abhi", "jaldi", "foran", "24 ghante mein",
                "permanent band ho jayega", "warna", "sirf aaj", "jaldi kare"],
    "hi": ["तुरंत", "अभी", "24 घंटे के अंदर", "आज ही", "नहीं तो बंद हो जाएगा",
           "ध्यान दें", "समय समाप्त", "ज़रूरी"],
    "te": ["తురంత", "ఇప్పుడే", "24 గంటలలో", "ఈ రోజే", "ఇలేకపోతే మూసివేస్తారు",
           "గమనించండి", "సమయం ముగుస్తుంది"],
}

# Hard negatives: LEGITIMATE transactional SMS. These are the messages that
# contain scary words ("account", "blocked", "verify") without being scams.
# This is the category our sources are worst at and the model most needs.
LEGIT_PATTERNS = {
    "otp": ["{bank}: Your OTP is {otp} valid for {mins} mins. Do not share it with anyone.",
            "{bank}: {otp} is your verification code. Valid for {mins} minutes.",
            "Your one time password is {otp}. Valid {mins} min. Never share with anyone."],
    "delivery": ["Your {platform} order {orderid} has been delivered. Rate your experience.",
                 "{platform}: Order {orderid} is out for delivery. Track in the app.",
                 "Delivered: {platform} order {orderid}. Keep the invoice for returns."],
    "appointment": ["Reminder: your appointment is on {date} at {time}. Please carry a photo ID.",
                    "Your {platform} booking is confirmed for {date}, {time}."],
    "salary_credit": ["Rs {amount} has been credited to your {bank} account. Bal {balance}.",
                     "{bank}: Salary of Rs {amount} credited. Available balance {balance}."],
    "transaction_alert": ["Rs {amount} debited from your {bank} A/C ending {acct} to {payee}. Bal {balance}.",
                          "{bank}: UPI payment of Rs {amount} to {payee} successful. UTR {utr}."],
    "autopay": ["{bank}: Rs {amount} will be auto-debited on {date} for your {platform} subscription.",
                "Your auto-pay of Rs {amount} for {platform} is scheduled on {date}."],
    "promo": ["{platform}: Get {discount}% off up to Rs {amount} this weekend. Code {code}.",
             "{telecom}: {data} data bonus activated. Valid {days} days. Reply STOP to opt out."],
}


def main():
    print("Loading audited sources...\n")
    ath_phish, ath_legit = load_atharva()
    ys = load_ysangam()
    ph5 = load_phishing5971()

    print(f"atharva phishing : {len(ath_phish)}")
    print(f"atharva legit    : {len(ath_legit)}")
    print(f"ysangam unique   : {len(ys)}")
    print(f"5971 phishing    : {len(ph5)}")

    # --- scam category vocabulary ------------------------------------------
    cat_words = collections.defaultdict(collections.Counter)
    for r in ys:
        if r["label"] == "1" and r["category"] and r["category"] != "none":
            for w in re.findall(r"[a-z']{4,}", r["text"].lower()):
                cat_words[r["category"]][w] += 1

    print("\nREAL VOCABULARY per ysangam scam category:")
    for cat, c in sorted(cat_words.items(), key=lambda kv: -len(kv[1])):
        top = [w for w, n in c.most_common(14)]
        print(f"  {cat:24} ({len(c):4} distinct) {top}")

    # --- entity co-occurrence in the real corpus ---------------------------
    print("\nENTITY mentions across real scam corpora:")
    blob = " ".join([t for t in ath_phish] + [r["text"] for r in ys]).lower()
    for role, names in ENTITIES.items():
        hits = {n: blob.count(n.lower()) for n in names}
        present = {k: v for k, v in hits.items() if v}
        print(f"  {role:9} {len(present):2}/{len(names)} seen: "
              f"{sorted(present.items(), key=lambda kv: -kv[1])[:8]}")

    # --- how do legit transactional messages actually look? ---------------
    print("\nLEGIT transactional samples from atharva (hard negatives):")
    for t in ath_legit[:12]:
        print(f"  {t[:110]}")

    # 5971 ham that mention scary words -- these are the real hard cases
    scary = [r for r in ph5 if r["label"] == "legit" and
             re.search(r"block|verif|account|kyc|otp|updat", r["text"], re.I)]
    print(f"\n5971 HAM containing scary keywords: {len(scary)} of "
          f"{sum(1 for r in ph5 if r['label'] == 'legit')} ham")
    for r in scary[:8]:
        print(f"  {r['text'][:110]}")

    out = ROOT / "data/interim/grounded_sources.json"
    out.write_text(json.dumps({
        "atharva_phishing": ath_phish,
        "atharva_legit": ath_legit,
        "ysangam_unique": ys,
        "entities": ENTITIES,
        "scam_pressure": SCAM_PRESSURE,
        "legit_patterns": LEGIT_PATTERNS,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()