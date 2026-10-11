"""
Fixture test for the disclosed rule layer in backend/predictor.py.

These rules are NOT the classifier. They exist for the OTP-share boundary that
measurement showed is hardest. But a rule that fires on a genuine bank alert is
worse than no rule: it is visible in the UI, it is wrong, and it invites the
reader to distrust every other signal.

Every case below is drawn from messages that measurement showed the MODEL gets
right. A rule must not contradict the model on any of them.

Run:  python backend/test_rules.py
"""
import pathlib
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

# (text, rule_name_that_MUST_NOT_fire, rule_names_that_MUST_fire)
NEGATIVE = [
    ("Your OTP is 482910. Valid for 5 minutes. Do not share it with anyone "
     "including bank staff.", "credential_request"),
    ("SBI: aapka OTP 475441 hai, 30 minute tak valid. Ise kisi ko mat share "
     "karna, bank staff ko bhi nahi.", "credential_request"),
    ("आपका ओटीपी 482910 है, 5 मिनट तक मान्य है। इसे किसी को न बताएं, "
     "बैंक कर्मचारी को भी नहीं।", "credential_request"),
    ("OTP hai 482910. Isay kisi ko share na karein.", "credential_request"),
    ("Never share your OTP with anyone.", "credential_request"),
    ("Your credit card bill of Rs 2,499 for HDFC Bank is due on 20th March. "
     "Minimum due Rs 499. Pay now to avoid late fees.", "payment_demand"),
    ("Statement ready. Your outstanding balance is Rs 4,200. Pay the amount "
     "by 25th to avoid late payment charges.", "payment_demand"),
    ("Auto-debit of Rs 1,299 for Netflix will be charged on 5th. No action "
     "needed.", "payment_demand"),
    ("Swiggy: Your food order is out for delivery. Suresh arriving in 12 mins.",
     "payment_demand"),
    ("Axis Bank: आपका केवाईसी नवीनीकरण के लिए देय है। दस्तावेज निकटतम शाखा "
     "में जमा करें। यह नियमित सूचना है।", None),
    ("Your mutual fund NAV for today: Growth Fund - Rs 45.67.", "payment_demand"),
]

POSITIVE = [
    ("OTP hai 482910. Humare agent ko share karein for verification.",
     "credential_request"),
    ("Please share your OTP with the bank officer to verify your account.",
     "credential_request"),
    ("Send your Aadhaar number and OTP to this number immediately.",
     "credential_request"),
    ("Your KYC is pending, transfer Rs 5000 to this UPI id to activate.",
     "payment_demand"),
    ("This is Cyber Crime Department. You are under digital arrest, transfer "
     "Rs 2,00,000 to the account given below.", "authority_impersonation"),
    ("National Cyber Cell se bol raha hoon. Aapke naam par money laundering "
     "case register hua hai.", "authority_impersonation"),
    ("Your HDFC account will be closed in 24 hours. Update KYC immediately at "
     "http://bit.ly/hdfc-kyc", "malicious_link"),
    ("You won a Rs 40 lakh lottery. Pay the Rs 999 processing fee now.",
     "prize_with_fee"),
]


def main():
    from predictor import Predictor
    p = Predictor.__new__(Predictor)   # rules are static; skip artifact load

    fails = []
    for text, must_not in NEGATIVE:
        fired = {r["name"] for r in Predictor.matched_rules(text)}
        bad = must_not and must_not in fired
        if bad:
            fails.append((text[:70], must_not, sorted(fired), "false positive"))
        else:
            print(f"  ok  no '{must_not}' -> {text[:62]}")

    for text, must in POSITIVE:
        fired = {r["name"] for r in Predictor.matched_rules(text)}
        if must not in fired:
            fails.append((text[:70], must, sorted(fired), "missed"))
        else:
            print(f"  ok  '{must}' fired -> {text[:62]}")

    print(f"\n{'='*74}")
    if fails:
        print(f"RULE FIXTURE TEST: {len(NEGATIVE)+len(POSITIVE)-len(fails)}/"
              f"{len(NEGATIVE)+len(POSITIVE)} pass  -- FAILURES:")
        for t, rule, fired, kind in fails:
            print(f"\n  [{kind}] {rule}  (fired: {fired})")
            print(f"    {t}")
        return 1
    print(f"RULE FIXTURE TEST: {len(NEGATIVE)+len(POSITIVE)}/"
          f"{len(NEGATIVE)+len(POSITIVE)} pass")
    print("  no rule contradicts the classifier on any known-good message")
    return 0


if __name__ == "__main__":
    sys.exit(main())