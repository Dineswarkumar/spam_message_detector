"""
Shared context guards — the single canonical definition, imported by BOTH the
corpus labeller (scripts/build_corpus.py) and the runtime rule layer
(backend/predictor.py).

Why these exist
---------------
The same surface words mean opposite things depending on a second word in the
sentence:

    "Your OTP is 482910. Do not share it with anyone."     <- legitimate
    "Share your OTP with our agent for verification."      <- scam

    "Card bill Rs 2,499 due. Pay to avoid late fee Rs 99." <- legitimate
    "Your account is blocked. Pay Rs 500 to this UPI id."  <- scam

A keyword list cannot separate these. The only separator is context: an
explicit PROHIBITION ("do not share") or a BILLING_CONTEXT noun ("bill",
"due", "statement"). These guards were added after measurement showed the
broad keywords were flipping 98 genuine OTP rows and 70 genuine transaction
alerts into review.

Why one file
------------
These were originally defined only in predictor.py and then duplicated into
the corpus labeller. Two copies of a safety guard drift, and a guard that
drifts between training-time labelling and runtime inference is worse than no
guard: the model learns from labels produced under one rule and is judged under
another. scripts/test_rules.py asserts both modules resolve to the same object.
"""
import re

# "do not share / don't send / mat batao" — the verb is negated, so a share
# request in this sentence is a warning to the reader, not a demand.
PROHIBITION = re.compile(
    r"(do\s*not|don't|dont|never|mat|nahi|nahin|na)\s*"
    r"(share|send|disclose|forward|paste|batao|bataaye|बताए|चेल्प)\w*"
    r"|share\s*(na|nahi|nahin|mat|karne)\w*"
    r"|(share|send)\s*karne\s*(mat|na)"
    r"|(never|do\s+not|don't)\s+(be\s+)?(share|disclos)"
    r"|(किसी\s*को\s*न|न\s*बताए|मत\s*भेज|साझा\s*न)",
    re.I)

# A payment demand sitting inside an ordinary billing sentence is a bill, not
# an activation/extortion demand. "Pay", "charge" and "Rs <n>" are weak on
# their own; "due date", "statement", "EMI", "auto-debit" make them legitimate.
BILLING_CONTEXT = re.compile(
    r"\b(bill|billing|statement|invoice|due|outstanding|"
    r"late\s+fee|auto-?debit|autopay|emi|instal?ment|repay|repayment|"
    r"salary|credit\s+card|minimum\s+due|balance|चार्ज|बिल|देय)\w*",
    re.I)

# The message tells the reader where to go and that no agent will ask for
# secrets. Present in genuine bank/government notices, absent in every scam
# template, because a scam must NOT tell you how to verify independently.
OFFICIAL_ROUTE = re.compile(
    r"(official\s+(net\s?banking|portal|website|app)|"
    r"on\s+our\s+(official\s+)?(website|app|portal)|"
    r"net\s?banking\s+(portal|se)|"
    r"हमारी\s+आधिकारिक|नेट\s*बैंकिंग|"
    r"అధికారిక|నెట్\s*బ్యాంకింగ్)",
    re.I)

# The message reports a FINISHED event: "your KYC has been updated", "Rs 500
# credited to your wallet", "no action is needed". Every scam template asks the
# reader to DO something in the future; none of them report a completed one.
# Added after the legitimate KYC-renewal twins of the sa11 KYC-banking scam
# were being pushed into review by `\bkyc\b.*(update|pending|verify)` and by
# Hindi `जमा` (which means both "deposit money [a demand]" and "has been
# credited [a report]").
COMPLETION = re.compile(
    r"(has\s+been|have\s+been|was|were|already|successfully|now)\s+"
    r"(updated|credited|processed|completed|linked|registered|declared|"
    r"generated|verified|issued|transferred|refunded|reactivated|ready)"
    r"|no\s+(further\s+|any\s+)?action\s+(is\s+)?(required|needed)"
    r"|is\s+valid\s+and\s+linked"
    r"|ho\s*gay(?:a|i|e)|ho\s*chuk(?:a|i|e)|update\s+ho|credit\s+ho|"
    r"jam[ao]\s+ho|successfully\s+(update|credited|linked|processed)"
    r"|kuch\s+(nahi|nahin)|koi\s+otp\s+required\s+nahi"
    r"|zaroorat\s+nahi|koi\s+action\s+(required\s+)?nahi"
    r"|हो(?:गया|गई|गए|गयी|गी|गा|ता|ते|चुका|चुकी|चुके|ने)"
    r"|अपडेट\s*हो|क्रेडिट\s*हो|जमा\s*हो|सफलतापूर्वक|स्वतः"
    r"|आवश्यकता\s*नहीं|कुछ\s*(करने\s*की\s*)?(ज़रूरत|जरूरत)"
    r"|అయ్యింది|అయ్యాయి|పూర్తి\s*చేయబడింది|సిద్ధంగా\s*ఉంది"
    r"|ఏమీ\s*చేయాలన్లేదు|జరురు\s*లేదు",
    re.I)

# An unresolved ASK aimed at the reader — the actual mechanics of a scam: a
# link to tap, an OTP to send, an amount to transfer, a document to upload.
# Paired against COMPLETION so that "your KYC has been updated. No action
# needed" is not confused with "update your KYC at this link now". A completed
# event followed by a live ask is still a scam and is NOT suppressed.
LIVE_ASK = re.compile(
    r"(click|tap|visit|open)\s+(the\s+)?(link|url|here|below)"
    r"|(send|share|submit|upload|paste|forward|transfer|deposit|provide)\s+"
    r"(your|your\s+a|a\s|this|the|all|details|aadhaar|pan|otp|cvv|password|"
    r"amount|rs\.?|it\s+to)"
    r"|(pay|transfer|deposit)\s+(rs\.?\s*\d|₹\s*\d|to\s+(this|our)\s+upi)"
    r"|(update|verify|submit)\s+(your\s+)?(kyc|aadhaar|pan|account\s+details)"
    r"|(तुरंत|अभी)\s*(भेज|शेयर|अपडेट|जमा|भुगतान|भेजें)"
    r"|(వెంటనే|ఇప్పుడే)\s*(పంపండి|అప్‌డేట్|జమా|చెల్లించండి)",
    re.I)


def completed_but_unclaimed(t):
    """True when the message reports finished work AND asks for nothing.

    This is the whole test for "legitimate status update that happens to use
    alarming vocabulary". A message with both a completion marker and a live
    ask is suspicious, so it stays suspicious.
    """
    return bool(COMPLETION.search(t)) and not bool(LIVE_ASK.search(t))