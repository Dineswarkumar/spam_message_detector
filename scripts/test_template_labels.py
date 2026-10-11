"""
Fixture test for the classifier's template-level expectations.

Every template in generate_synthetic.py and generate_marketing.py exists in five
languages and has ONE correct label by construction. This asserts the labeller
reaches that label for every template x language combination. It exists because
the non-Latin fraud patterns introduced in v2 were too broad: bare `शुल्क`
(charge), bare `केवाईसी` (KYC) and bare `ఓటీపీ` (OTP) matched GENUINE bank
notices and flipped 98 legitimate OTP rows into review.

Run:  python scripts/test_template_labels.py
"""
import importlib.util
import pathlib
import random
import sys
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    bc = load("bc", ROOT / "scripts/build_corpus.py")
    gs = load("gs", ROOT / "scripts/generate_synthetic.py")
    gm = load("gm", ROOT / "scripts/generate_marketing.py")

    cases = []   # (template_id, lang, expected_target_label, text)
    for tid, cat, var in gs.SCAM_TEMPLATES:
        for lang, tmpl in var.items():
            cases.append((tid, lang, "scam", tmpl))
    for tid, cat, var in gs.LEGIT_TEMPLATES:
        for lang, tmpl in var.items():
            cases.append((tid, lang, "legitimate", tmpl))
    for tid, cat, var in gm.MARKETING_TEMPLATES:
        for lang, tmpl in var.items():
            cases.append((tid, lang, "marketing_spam", tmpl))

    # The classifier needs concrete slot values to see real text.
    slots = dict(gs.slot_values(random.Random(0)))
    slots.update(gm.slots(random.Random(0)))

    fails = []
    for tid, lang, expected, tmpl in cases:
        try:
            text = tmpl.format(**slots)
        except KeyError as e:
            fails.append((tid, lang, expected, f"SLOT ERROR {e}", ""))
            continue
        # synthetic rows carry original_label = legit/scam/marketing_spam
        orig = "scam" if expected == "scam" else (
            "marketing_spam" if expected == "marketing_spam" else "legit")
        got, reason = bc.classify(text, orig)
        if got != expected:
            fails.append((tid, lang, expected, got, text))

    total = len(cases)
    print("=" * 76)
    print(f"TEMPLATE LABEL FIXTURE TEST: {total - len(fails)}/{total} pass")
    print("=" * 76)

    # -----------------------------------------------------------------------
    # Anti-suppression fixtures for the context guards.
    #
    # The template sweep above cannot catch the one way PROHIBITION /
    # BILLING_CONTEXT / completed_but_unclaimed can hurt us: a scam that
    # deliberately borrows legit phrasing. These are hand-written for that.
    # Each must STILL classify as scam. If a guard ever gets loosened enough to
    # rescue one of these, the guard is the bug, not the message.
    # -----------------------------------------------------------------------
    guard_fixtures = [
        ("scam + do-not-share wrapper", "scam",
         "Your OTP is 482910. Do not share it with anyone. But first, send Rs "
         "5000 to upi.securepay1234@ybl to reactivate your account."),
        ("scam + completion wrapper", "scam",
         "Your KYC has been updated successfully. No action needed. However to "
         "verify, share your Aadhaar and OTP with our agent now."),
        ("scam + completion + live ask", "scam",
         "Your EMI has been debited. No further action required. To confirm the "
         "mandate, update your KYC immediately at http://sbi-kyc-update.co.in/secure/40219."),
        ("scam + billing vocabulary", "scam",
         "Your outstanding bill is Rs 49,900. This is your final notice. Pay "
         "immediately to this UPI id upi.paynow8899@okaxis or your account will "
         "be permanently blocked."),
        ("scam + official-portal wording", "scam",
         "HDFC: Your account will be suspended in 24 hours. Immediately visit "
         "our official website http://hdfc-update.co.in/secure/55123 and pay the "
         "pending charge of Rs 2500."),
        ("scam + 'already updated'", "scam",
         "Aadhaar ending 1234 has been linked. No action needed. But for full "
         "verification call our agent immediately and share your PIN."),
        ("scam (hi) + क्रेडिट हो गया", "scam",
         "आपका खाता क्रेडिट हो गया है। अब कुछ करने की आवश्यकता नहीं है। लेकिन "
         "सत्यापन के लिए तुरंत अपना ओटीपी और आधार इस नंबर पर भेजें।"),
        ("scam (te) + అప్‌డేట్ అయ్యింది", "scam",
         "మీ KYC అప్‌డేట్ అయ్యింది. ఏమీ చేయాలన్లేదు. కానీ ధృవీకరణ కోసం వెంటనే "
         "మీ OTP మరియు ఆధార్ ఈ నంబర్‌కు పంపండి."),
        ("scam + no-action-needed + payment", "scam",
         "Nothing is pending on your account, no action needed. Just send Rs "
         "999 processing fee to claim your Rs 40 lakh lottery prize."),
    ]

    guard_fails = []
    for name, expected, text in guard_fixtures:
        got, reason = bc.classify(text, "scam")
        if got != expected:
            guard_fails.append((name, expected, got, reason, text))

    print(f"GUARD ANTI-SUPPRESSION: {len(guard_fixtures) - len(guard_fails)}"
          f"/{len(guard_fixtures)} pass")
    for name, exp, got, reason, text in guard_fails:
        print(f"  FAIL {name}: expected {exp}, got {got} ({reason})")

    if not fails and not guard_fails:
        print("\n  all templates x languages classify correctly")
        print("  no guard rescued a scam that borrowed legitimate phrasing")
        return 0

    if fails:
        by_tid = Counter((f[0], f[2], f[3]) for f in fails)
        print(f"\n{len(fails)} TEMPLATE FAILURES, grouped by template:\n")
        for (tid, exp, got), n in sorted(by_tid.items()):
            print(f"  {tid:8} expected {exp:15} got {got:15} ({n} langs)")

        print("\nsample failing texts:")
        for tid, lang, exp, got, text in fails[:14]:
            print(f"\n  {tid} [{lang}] expected={exp} got={got}")
            print(f"    {text[:145]}")

    return 1


if __name__ == "__main__":
    sys.exit(main())