"""
Unified corpus assembler + three-class labeller.

LABEL SCHEME (as specified):
  legitimate      expected personal / delivery / account / transactional.
                  e.g. a genuine bank OTP that says not to share it.
  marketing_spam  unsolicited advertising or bulk promotion, NO attempt to
                  steal money or credentials. e.g. quiz-show promotion.
  scam            deceives or pressures to send money, reveal credentials/OTP,
                  or follow a malicious link.
  review          cannot confidently tell -> EXCLUDED from training, written
                  to a review file for human resolution.

Rules applied in order:
  - If both promotional AND fraudulent  -> scam.
  - If not confidently classifiable      -> review.
  - original spam/ham labels are NEVER overwritten; they live in
    original_label while target_label carries the new scheme.

Outputs (data/processed/):
  corpus_labeled.csv   every row, with original_label AND target_label
  review_queue.csv     uncertain rows only, with a reason
  corpus_train_ready.csv  target_label in {legitimate, marketing_spam, scam}
                        with duplicate groups attached (for grouped splits)
  near_duplicate_groups.csv  groups of related messages that must stay together
"""
import csv
import importlib.util
import json
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
DS = ROOT / "dataset"
OUT = ROOT / "data/processed"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Script detection
# ---------------------------------------------------------------------------
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

HINGLISH = {
    "aap", "aapka", "aapki", "aapke", "hai", "hain", "karo", "kare", "karein",
    "karna", "kripya", "turant", "abhi", "bilkul", "nahi", "nhi", "mat", "sir",
    "madam", "khatam", "bhejo", "khul", "block", "dena", "dunga", "dungi",
    "waqt", "jaldi", "pakka", "dhyan", "shukriya", "namaste", "accha", "paisa",
    "rupaye", "bharosa", "jaldi",
}
TANGLISH = {
    "nuvvu", "meeku", "garu", "kavali", "undi", "chalundi", "pettu", "petta",
    "aapavu", "raaledu", "nenu", "em", "iki", "kurchi", "vachayi", "theeyali",
    "saledu", "paisalu", "cheppali", "cheppu", "vanki", "vandi", "manchi",
    "sundari", "dhanyaludu", "krupya", "kaani", "aaputha", "band", "block",
    "surakshalu", "ekkadiki", "chesavandi", "pani", "cheyyali",
}


def scripts_of(text):
    out = set()
    for ch in text:
        cp = ord(ch)
        for name, (lo, hi) in RANGES.items():
            if lo <= cp <= hi:
                out.add(name)
    return out


def language_of(text):
    """Return (language, script). One message is assigned one primary language;
    script is measured, never assumed."""
    s = scripts_of(text)
    non_latin = s - {"latin"}
    if "devanagari" in s:
        return ("hindi", "devanagari") if "latin" not in s else ("hinglish", "mixed_devanagari_latin")
    if "telugu" in s:
        return ("telugu", "telugu") if "latin" not in s else ("tenglish", "mixed_telugu_latin")
    if "tamil" in s:
        return ("tamil", "tamil")
    if "kannada" in s:
        return ("kannada", "kannada")
    if "malayalam" in s:
        return ("malayalam", "malayalam")
    if "bengali" in s:
        return ("bengali", "bengali")
    if "gujarati" in s:
        return ("gujarati", "gujarati")
    if "arabic" in s:
        return ("urdu", "arabic")
    # latin only -> discriminate romanized registers
    words = set(re.findall(r"[a-z']+", text.lower()))
    if len(words & TANGLISH) >= 2:
        return "tenglish", "latin"
    if len(words & HINGLISH) >= 2:
        return "hinglish", "latin"
    return "english", "latin"


# ---------------------------------------------------------------------------
# Fraud / promotion signals. These decide marketing_spam vs scam.
# A message containing ANY strong fraud signal is scam even if promotional.
# ---------------------------------------------------------------------------
STRONG_FRAUD = [
    # credential / OTP theft.
    # NOTE: a BARE `otp` or `one time password` must NOT be fraud -- a genuine
    # bank OTP says "your OTP is 123456". Only a REQUEST for one is fraud. The
    # earlier bare `\botp\b` sent every legitimate OTP notice to `review`.
    r"(share|send|provide|confirm|give|enter|share).{0,25}(\botp\b|one\s?time\s?pass)",
    r"(\botp\b|one\s?time\s?pass).{0,25}(share|send|bhej|bhejo|provide|confirm|enter)",
    r"confirm.*\botp\b", r"provide.*\botp\b",
    # account takeover / KYC closure pressure
    r"\bkyc\b.*(update|pending|expire|block|complete|verify)",
    r"(account|kyc).*(permanently|suspend|block|deactivat|freez|closure)",
    r"(block|suspend|deactivat|freez).*(account|kyc|card)",
    r"re-?activat", r"unblock", r"re-?open.*account",
    # money solicitation. `bhej/bhejo/...` are the Romanized-Hindi spellings
    # of "send" and occur constantly in Hinglish scams; omitting them let
    # sa07/sa10 fall through to review.
    r"(transfer|send|sent|wire|pay|bhej|bhejo|bhejein|bheje|bhejna).{0,40}"
    r"(rs\.?|₹|rupees|lakh|crore|amount|upi|account)",
    r"(transfer|send|pay|bhej|bhejo).{0,40}(upi|account no|ifsc|bank account)",
    # Hinglish routinely states the amount first and the send-verb second:
    # "Rs 2,499 chahiye ... UPI par bhej do". Needs the reverse order too.
    # Word boundaries are required: without them `pay` matched inside
    # "UPI payment successful", flagging genuine transaction alerts as fraud.
    r"(rs\.?\s?[\d,]+|₹\s?[\d,]+|\bupi\b).{0,60}"
    r"\b(bhej|bhejo|bhejein|bhejiye|transfer|send|pay)\b",
    r"(gift|voucher|prize|reward|winning|lottery).{0,60}(fee|charge|pay|transfer|claim)",
    # A stated fee is only fraud when it is DEMANDED. "No registration fee"
    # and "zero processing charge" are denials, so guard with lookbehinds.
    r"(?<!no\s)(?<!not\s)(?<!never\s)(?<!zero\s)(?<!koi\s)(?<!कोई\s)"
    r"(processing|registration|clearance|customs|security)\s*(fee|charge)"
    # a fee noun followed by a negation is a DISCLAIMER, not a demand
    r"(?!\s*(emi|nahi|nahi|koi|kabhi|ever|never|zero|no\b|not\b|"
    r"ఎప్పుడూ|లేదు|कभी|नहीं|कभी\s*नहीं))",
    r"claim.{0,30}(prize|reward|gift|voucher|amount|bonus)",
    # malicious link solicitation
    r"(click|tap|visit|open|update|verify|confirm).{0,30}(link|url|http|www\.)",
    r"http\S+.*(verify|kyc|update|claim|secure|account|login)",
    r"bit\.ly|tinyurl|t\.co|short\.link|\.tk/|bit\.do",
    # impersonation of authority
    r"(police|cyber ?crime|crime branch|ed ?police|sit|cbi|it ?police).{0,60}"
    r"(arrest|case|fraud|notice|probe|investigation|warrant|compounding)",
    r"digital\s+arrest",
    # pressure / threats
    r"(legal\s+action|police\s+will|case\s+will\s+be|arrest\s+hoga|"
    r"jail|fine\s+of|prosecut)",
    # A countdown must be a DEADLINE demand, not a validity window. A bare
    # `\d+\s*hours?` matched "Valid for 48 hours" in a genuine promotion, which
    # is why lg13 promo rows were being sent to review as suspected fraud.
    r"within\s*\d+\s*(min|hour|hr|day)",
    r"\d+\s*(hours?|hrs?|घंटे|घंटों|గంటల)\s*(में|లో|mein)",
    r"last\s+(warning|chance)", r"final\s+warning", r"expires?\s+today",
    r"avoid\s+(permanent|legal)", r"do\s+not\s+(ignore|delay)",
    # personal data solicitation
    r"(send|share|provide|bhej|bhejo|bhejein|bheje|bhejiye).{0,40}"
    r"(aadhaar|aadhar|pan\s*(no|number)|cvv|card\s*no)",
    # reverse order: "apna Aadhaar number, OTP aur bank details ... par bhejein"
    r"(aadhaar|aadhar|pan\s*(no|number)|cvv).{0,60}"
    r"(bhej|bhejo|bhejein|bheje|bhejiye|send|share|provide)",
    r"aadhaar.{0,30}(update|link|verify|send)",
]

# Non-English fraud signals. Added after the audit showed Hindi/Telugu scam
# counts collapsing to zero: the banks above are almost entirely English
# regexes, so a Devanagari or Telugu scam was only ever caught by an embedded
# URL or digit run.
#
# RULE: every pattern must require a DEMAND or COERCION, never a bare topic
# noun. The first version of this bank matched bare शुल्क (charge), bare
# केवाईसी (KYC) and bare ఓటీపీ (OTP) -- which flipped 98 genuine OTP rows and
# every genuine bill reminder into `review` and turned quiz-SMS marketing into
# scam. `scripts/test_template_labels.py` guards against that regression.
NON_LATIN_FRAUD = [
    # ---- Devanagari: OTP solicited (not merely stated) ----
    # Latin "otp" is accepted alongside the Indic transliteration because
    # code-mixed messages routinely write the acronym in Roman script inside
    # otherwise Hindi text, and the Indic-only pattern missed those entirely.
    r"(ओटीपी|\botp\b).{0,60}(साझा|भेज|दें|बताए|शेयर|share|send)",
    r"(साझा|भेज|बताए|शेयर|share|send).{0,60}(ओटीपी|\botp\b)",
    r"(साझा|शेयर|share).{0,30}(आधार|पैन|सीवीवी|\baadhaar\b|\bpan\b|\bcvv\b)",
    # ---- Devanagari: money demand. The demand verb frequently comes AFTER the
    # amount ("2,499 रुपये चाहिए ... अभी UPI पर भेज दें"), so both orders needed.
    r"(भेज|भेजें|भेजिए|जमा|करें|दे\s*दें|क्रेडिट).{0,60}"
    r"(रुपये|रुपए|रूपये|upi|खाता|रकम)",
    r"(रुपये|रुपए|रूपये|upi).{0,60}(भेज|जमा|भेजें|भेजिए|दे\s*दें)",
    # ---- Devanagari: account/card closed under threat ----
    r"(खाता|अकाउंट|कार्ड).{0,30}(ब्लॉक|निलंबित|बंद हो|फ्रीज)",
    r"(ब्लॉक|निलंबित|फ्रीज).{0,30}(खाता|अकाउंट|कार्ड)",
    # ---- Devanagari: KYC used as a pretext, not a routine renewal ----
    r"(केवाईसी|केवाईसी|\bkyc\b).{0,40}(अपडेट|अधूरा|निलंबित|बंद हो|फ्रीज|पेंडिंग)",
    r"(अपडेट|निलंबित|अधूरा).{0,30}केवाईसी",
    # ---- Devanagari: authority impersonation ----
    r"(पुलिस|साइबर\s*सेल|सीबीआई|एनसीबी|ईडी)",
    r"(गिरफ़्तार|वारंट|मुकदमा|कानूनी\s*कार्रवाई)",
    r"(मनी\s*लॉन्ड्रिंग|नकली\s*खाता|धोखाधड़ी\s*केस)",
    # ---- Devanagari: prize contingent on payment. A fee noun alone is not enough
# -- "कोई पंजीकरण शुल्क कभी नहीं" is a DENIAL. Require a real amount/payment
# target on one side of it.
    r"(जीत|जीते|जीतने|जीती).{0,20}(रुपये|रुपए|लाख)",
    r"(\d[\d,]*|रुपये|रुपए|₹).{0,30}"
    r"(प्रोसेसिंग\s*फीस|पंजीकरण\s*शुल्क|क्लियरेंस\s*चार्ज)",
    r"(प्रोसेसिंग\s*फीस|पंजीकरण\s*शुल्क|क्लियरेंस\s*चार्ज).{0,40}"
    r"(रुपये|रुपए|upi|खाता|\d[\d,]*\s*रुपये)",
    # ---- Telugu: OTP solicited (not merely stated) ----
    r"(ఓటీపీ|\botp\b).{0,60}(పంపండి|పంచుకోండి|ఇవ్వండి|బాధితపడం|send|share)",
    r"(పంపండి|పంచుకోండి|send|share).{0,60}(ఓటీపీ|\botp\b)",
    # ---- Telugu: money demand (both word orders) ----
    r"(పంపండి|చెల్లించండి|వేయండి|జమా).{0,60}"
    r"(రూపాయలు|యుపిఐ|ఖాతా)",
    r"(రూపాయలు|యుపిఐ).{0,60}(పంపండి|చెల్లించండి|జమా)",
    # ---- Telugu: account/card closed under threat ----
    r"(ఖాతా|అక్కౌంట్|కార్డ్).{0,30}(మూసివేస్తారు|నిలిపివేశారు|బ్లాక్|ఫ్రీజ్)",
    r"(మూసివేస్తారు|నిలిపివేశారు).{0,30}(ఖాతా|అక్కౌంట్)",
    # ---- Telugu: KYC used as a pretext ----
    r"(కెవైసీ|కేవైసీ|\bkyc\b).{0,40}(పెండింగ్|నిలిపివేస్తారు|మూసివేస్తారు)",
    # ---- Telugu: authority impersonation ----
    r"(పోలీస్|సైబర్\s*సెల్|సీబీఐ|ఎన్‌సీబీ)",
    r"(అరెస్ట్|వారంట్|నకిలీ\s*ఖాతా)",
    # ---- Telugu: prize contingent on payment (amount required, both orders) ----
    r"(గెలిచారు|బహుమతి)",
    r"(\d[\d,]*|రూపాయలు).{0,30}"
    r"(ప్రాసెసింగ్\s*ఫీజు|రిజిస్ట్రేషన్\s*ఫీజు|క్లియరెన్స్\s*ఛార్జీ)",
    r"(ప్రాసెసింగ్\s*ఫీజు|రిజిస్ట్రేషన్\s*ఫీజు|క్లియరెన్స్\s*ఛార్జీ).{0,40}"
    r"(రూపాయలు|యుపిఐ|ఖాతా|\d[\d,]*\s*రూపాయలు)",
]

STRONG_FRAUD = STRONG_FRAUD + NON_LATIN_FRAUD

WEAK_FRAUD = [
    r"\brefer\b", r"refer\s+\d+", r"win\b", r"winner", r"congratulat",
    r"offer\b", r"discount", r"cashback", r"free\b", r"click\s+here",
    r"promo", r"deal", r"sale\b", r"limited\s+time", r"exclusive",
]

PROMOTIONAL = [
    r"\bquiz\b", r"reply\s+[1-9]", r"horoscope", r"tv\s+channel",
    r"unsubscribe", r"reply\s+stop\b", r"offers?\b.*\bcall\b",
    r"ieee\b", r"project\s+(report|code)", r"real\s?estate", r"flat\s+villa",
    r"buy\s+(now|one\s+get)", r"discount\s+\d+%", r"free\s+delivery",
    r"order\s+(now|placed)", r"limited\s+period", r"dear\s+(user|customer|friend)",
    r"call\s+(now|today|immediately)", r"promo\s+code", r"scheme\b",
]

# Legitimate transactional markers: real bank/OTT/telecom notifications.
TRANSACTIONAL = [
    r"your\s+otp", r"otp\s+is\s+\d", r"\bdo\s+not\s+share\b", r"valid\s+for\s+\d+\s*min",
    r"has\s+been\s+(credited|debited)", r"available\s+balance", r"\bbalance\b.{0,20}rs",
    r"order\s+\d{6,}", r"has\s+been\s+delivered", r"out\s+for\s+delivery",
    r"appointment", r"booking\s+(is\s+)?confirm", r"\bpnr\b", r"salary",
    r"auto-?pay", r"autopay", r"due\s+on", r"statement", r"invoice",
    r"your\s+order", r"track\s+(your\s+)?order", r"shipped", r"arriving",
    r"\bwithdraw", r"atm\s+card", r"aadhaar\s+is\s+valid", r"dear\s+(customer|user)",
    r"thanks?\s+for\s+shopping", r"your\s+payment", r"transaction\s+(is\s+)?successful",
    r"\bdear\s+(mr|mrs|ms)\b",
    # Devanagari transactional markers
    r"आपका\s+ओटीपी", r"ओटीपी.{0,30}(मान्य|मिनट)",
    r"(किसी\s+को\s+न\s+बताएं|बताएं)", r"बैंक\s+कर्मचारी",
    r"(जमा\s+हो\s+गए|जमा\s+हो\s+गई|डेबिट\s+हुए)", r"उपलब्ध\s+शेष",
    r"क्रेडिट\s*कार्ड\s*बिल", r"(बिल.{0,30}देय|देय\s+है)", r"न्यूनतम\s+देय",
    r"(आपका\s+ऑर्डर|डिलीवर|आपीटमेंट|अपॉइंटमेंट)", r"सैलरी",
    r"(अतिरिक्त|डेटा).{0,20}जोड़", r"वैधता",
    # Telugu transactional markers
    r"మీ\s+(OTP|ఓటీపీ)", r"ప్రశస్త్రం", r"చెప్పకండి", r"బ్యాంక్\s*ఉద్యోగుల",
    r"క్రెడిట్\s*కార్డ్\s*బిల్", r"చెల్లించాలి", r"ఆలస్య\s*రుసుం",
    r"(జమ|ఖాతా).{0,20}అవుతాయి", r"ఆర్డర్", r"డెలివరీ", r"అపాయింట్మెంట్",
    r"జీతం", r"డేటా", r"వెలిడిటీ",
]

# Promotional signals in Hindi and Telugu. Without these, non-English marketing
# templates matched no promotional pattern and fell through to `review`, which
# silently removed ~40% of the marketing_spam class from every Indian language.
PROMOTIONAL_NON_LATIN = [
    # Devanagari
    r"(मुफ़्त|मुफ्त|फ्री)", r"(छूट|डिस्काउंट)", r"(ऑफर|प्रचार|विज्ञापन)",
    r"(प्लॉट|फ्लैट|विला)", r"\bEMI\b", r"(ईएमआई)",
    r"(प्रोजेक्ट|कोचिंग|बैच|डेमो\s*क्लास|ट्यूशन)",
    r"(रजिस्ट्रेशन|रजिस्टर).{0,20}फी", r"(सीटें|सीटें\s*सीमित)",
    r"(सेल|स्टोर|फ्री\s*डिलीवरी)", r"(ट्रायल\s*डिल)",
    r"(हॉरoscope|कुंडली|सुविचार|करियर)",
    r"\bSTOP\b", r"(उत्तर\s*दें|रिप्लाई)",
    # Telugu
    r"ఉచిత", r"తగ్గింపు", r"ఆఫర్", r"(ప్లాట్|ఫ్లాట్)", r"\bEMI\b",
    r"(రిజిస్ట్రేషన్).{0,20}ఫీజు", r"(సేట్లు|సీట్లు)",
    r"(సేల్|స్టోర్|免ఫ్రీ)", r"ఫ్రీ",
    r"(హారోస్కోప్|జాతక|శ్లోకం|కెరీర్)",
    r"\bSTOP\b", r"(సమాధానం|రిప్లై)",
]

PERSONAL = [
    r"\?\?+", r"\bhaha+h+\b", r"\blol\b", r"\bok\b", r"\bk\b\s*$",
    r"\blve\b", r"\bwanna\b", r"\btmr\b", r"\bttyl\b", r"\bgr8\b",
    r"\bmeet\b", r"\bcall\s+me\b", r"\bwhere\s+are\s+you\b", r"\bsingle\b",
    r"\bmovie\b", r"\bparty\b", r"\bfood\b", r"\bclass\b",
]

PROMOTIONAL = PROMOTIONAL + PROMOTIONAL_NON_LATIN + [
    # discount / offer phrasing that the original bank missed
    r"\d+\s*%\s*off", r"\bmax(imum)?\b", r"\bvalid\s+for\s+\d+\s*hours?",
    r"\bcode\s+[A-Z0-9]{3,10}\b", r"\buse\s+code\b",
    r"lucky\s+draw", r"selected\s+for", r"no\s+purchase\s+needed",
    r"collect\s+at\s+our", r"\bstore\b",
    r"early\s+bird", r"family\s+pack(age)?", r"\btickets?\b", r"festival",
    r"unlimited\s+movies", r"first\s+month\s+free", r"\bott\b",
    r"marketing\s+package", r"rate\s*card", r"small\s+business",
    r"reply\s+(package|play|pod|claim|d|pod\b)",
    r"work\s+from\s+home", r"shortlisted", r"no\s+experience",
    r"\bstart\s+now\b", r"\bapply\b", r"\bregister\s+now\b",
    r"\bspy\b.*\bmovie", r"premium\s+rate", r"\bper\s+sms\b",
    r"donate", r"tal\s*to\s*8\d{3}", r"\bcall\s+0?9\d",
    # Hindi / Telugu equivalents
    r"(लकी\s*ड्रॉ|लक्की\s*ड्रॉ)", r"(లక్కీ\s*డ్రాలో)",
    r"\bटिकट\b", r"\bటిక్కెట్\b", r"(संगीत\s*महोत्सव|మహోత్సవం)",
    r"रेट\s*कार्ड", r"రేట్\s*కార్డ్", r"स्पीकर", r"स्पీకర్",
    r"(डिस्काउंट|ऑफर)\s*\d+%", r"(తగ్గింపు|ఆఫర్)\s*\d+%",
    r"(वर्क\s*फ्रॉम\s*होम|కోసం\s*పని)", r"work\s+from\s+home",
    r"(रिफर|బంధుమిత్రుడిని)",
    r"(निःशुल्क|फिल्में|ऐप\s*पर|स्ट्रीमिंग)", r"(ఉచితంగా|స్ట్రీమింగ్)",
    # recruitment advertising (Hinglish / Devanagari / Telugu)
    r"(work\s+from\s+home)", r"(घर\s*से\s*काम|वर्क\s*फ्रॉम\s*होम|रिमोट)",
    r"(इंटर्न|नौकरी|फ्रेशर)", r"(ఇంటర్న్|ఉద్యోగం)", r"\bfreshers\b",
    r"(విద్యార్థులు|ఫ్రెషర్ల|అభ్యర్థులు)", r"(इंटरन|फ्रेशर|उम्मीदवार)",
]

MALICIOUS_INDICATOR = re.compile("|".join(STRONG_FRAUD), re.I)
WEAK_FRAUD_R = re.compile("|".join(WEAK_FRAUD), re.I)
PROMO_R = re.compile("|".join(PROMOTIONAL), re.I)
TRANSACTIONAL_R = re.compile("|".join(TRANSACTIONAL), re.I)
PERSONAL_R = re.compile("|".join(PERSONAL), re.I)
URL_R = re.compile(r"https?://|www\.|bit\.ly|tinyurl|\.com|\.in/|\.tk/", re.I)
PHONE_R = re.compile(r"\b(?:\+?91[\- ]?)?[6-9]\d{9}\b")
SHORT_TEXT_R = re.compile(r"^\W*$")

# Context guards, imported from backend/guards.py so the corpus labeller and
# the runtime rule layer judge a message with identical rules. See that file
# for why two copies of a safety guard is a defect.
sys.path.insert(0, str(ROOT / "backend"))
from guards import PROHIBITION, BILLING_CONTEXT, OFFICIAL_ROUTE, completed_but_unclaimed  # noqa: E402


def classify(text, original_label):
    """Return (target_label, reason). Never returns None -- 'review' is explicit.

    PRECEDENCE (corrected 2026-10-09):
      "If a message is both promotional and fraudulent -> scam."

    The previous implementation violated this. It downgraded a message to
    marketing_spam whenever it was promotional AND matched a strong fraud
    signal, PROVIDED it did not also contain one of eight literal English
    keywords (otp|aadhaar|pan no|cvv|account no|kyc|verify|update|transfer|pay).
    So a promo carrying an hour-countdown threat, a legal threat or police
    impersonation was labelled marketing_spam purely because it phrased the
    money demand differently -- i.e. the outcome depended on vocabulary rather
    than on conduct.

    Now: ANY strong fraud signal yields scam, unconditionally. Fraud beats
    promotion, always. The English keyword list is gone as a gate.
    """
    t = (text or "").strip()
    if not t:
        return "review", "empty message"

    fraud = bool(MALICIOUS_INDICATOR.search(t))
    promo = bool(PROMO_R.search(t))
    trans = bool(TRANSACTIONAL_R.search(t))
    personal = bool(PERSONAL_R.search(t))
    weak = bool(WEAK_FRAUD_R.search(t))
    url = bool(URL_R.search(t))
    phone = bool(PHONE_R.search(t))

    # --- ham candidates: usually legitimate, but verify -----------------------
    if original_label in ("ham", "legit", "0"):
        # A "ham" row that screams fraud is more likely a mislabelled scam than
        # a genuine transaction. Send to review rather than guess.
        if fraud and not trans:
            # A ham row matching MALICIOUS_INDICATOR is usually a mislabelled
            # scam, so it goes to review rather than a guess. But two shapes
            # are explained by context, and they are precisely the hard
            # negatives this corpus needs most:
            #   - an explicit prohibition ("do not share this OTP")
            #   - a payment demand inside an ordinary billing sentence
            # Without these guards the labeller discarded the legitimate twin
            # of every KYC / bill / OTP scam template, which is how a model
            # learns "KYC reminder -> scam". Same guards as the runtime rule
            # layer, imported from backend/guards.py so they cannot drift.
            if PROHIBITION.search(t):
                return "legitimate", "ham row carries an explicit do-not-share; verb is negated"
            if BILLING_CONTEXT.search(t):
                return "legitimate", "ham row's payment demand sits inside a billing context"
            if OFFICIAL_ROUTE.search(t) and not url:
                return "legitimate", "ham row points to an official verification route"
            if completed_but_unclaimed(t):
                return "legitimate", "ham row reports finished work and asks for nothing"
            return "review", "ham row carries strong fraud signals; verify label"
        if trans or personal:
            return "legitimate", "transactional/personal marker"
        if len(t) < 4:
            return "review", "too short to classify"
        return "legitimate", "original ham, no fraud signals"

    # --- spam candidates: split marketing vs scam ---------------------------
    # Rule 1 applies first and without exception.
    if fraud:
        if promo:
            return "scam", "strong fraud signal AND promotional -> fraud wins"
        return "scam", "strong fraud signal"
    if promo or weak:
        return "marketing_spam", "promotional/bulk, no fraud signal"
    if url or phone:
        # has contact detail but nothing else -> ambiguous, could be a business
        # promotion or a low-effort scam
        return "review", "url/phone but no clear fraud or promo signal"
    return "review", "spam label but no decisive signal"


# ---------------------------------------------------------------------------
# Loaders for every source
# ---------------------------------------------------------------------------
def norm(t):
    return " ".join((t or "").lower().split())


def load_sources():
    rows = []

    def add(text, orig, source, src_id=None, template_id=None,
            category=None, real=True, lang=None):
        text = (text or "").strip()
        if not text:
            return
        lg, sc = language_of(text)
        rows.append({
            "text": text,
            "original_label": orig,
            "source": source,
            "source_id": src_id,
            "template_id": template_id,
            "category": category,
            "language": lang or lg,
            "script": sc,
            "real_or_synthetic": "real" if real else "synthetic",
            "_norm": norm(text),
        })

    # 1. UCI
    p = DS / "01_uci_sms_spam/SMSSpamCollection"
    if p.exists():
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines()):
            if "\t" in line:
                lab, _, txt = line.partition("\t")
                add(txt, lab.strip().lower(), "uci", src_id=f"uci:{i}")

    # 2. Indian crowdsourced 2011 (Yadav et al.)
    p = DS / ("-SMS-Spam-Classification-on-Indian-Dataset-A-Crowdsourced-"
              "Collection-of-Hindi-and-English-Messages-main/indian_spam.csv")
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as fh:
            for i, r in enumerate(csv.DictReader(fh)):
                add(r["v2"], r["v1"].strip().lower(), "indian2011", src_id=f"ind2011:{i}")

    # 3. SMS Phishing 5971 (smishing / spam / ham)
    p = DS / ("SMS PHISHING DATASET FOR MACHINE LEARNING AND PATTERN "
              "RECOGNITION/Dataset_5971.csv")
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as fh:
            for i, r in enumerate(csv.DictReader(fh)):
                lab = (r.get("LABEL") or "").strip().lower()
                orig = {"smishing": "smishing", "spam": "spam", "ham": "ham"}.get(lab, lab)
                add(r.get("TEXT"), orig, "phishing5971", src_id=f"p5971:{i}")

    # 4. Atharva taxonomy
    p = DS / "04_phishing_taxonomy_atharva/atharva_dataset.py"
    if p.exists():
        spec = importlib.util.spec_from_file_location("ath", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for i, x in enumerate(getattr(mod, "PHISHING_MESSAGES", []) or []):
            t = x.get("message", "") if isinstance(x, dict) else str(x)
            add(t, "spam", "atharva", src_id=f"ath_p:{i}", category="phishing")
        for i, x in enumerate(getattr(mod, "LEGIT_MESSAGES", []) or []):
            t = x.get("message", "") if isinstance(x, dict) else str(x)
            add(t, "ham", "atharva", src_id=f"ath_l:{i}")

    # 5. ysangam (dedup on the way in)
    p = DS / "03_needs_verification/ysangam_india_cyber_scam.csv"
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as fh:
            seen = set()
            for i, r in enumerate(csv.DictReader(fh)):
                k = norm(r.get("text"))
                if not k or k in seen:
                    continue
                seen.add(k)
                orig = "spam" if r.get("label") == "1" else "ham"
                add(r.get("text"), orig, "ysangam", src_id=f"ys:{i}",
                    category=r.get("scam_category"))

    # 6. legacy multilingual (salvage uniques)
    p = DS / "02_legacy_old_repo_rakshasutra/multilingual_fraud_dataset.csv"
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as fh:
            for i, r in enumerate(csv.DictReader(fh)):
                add(r["text"], r["label"].strip().lower(), "legacy_ml",
                    src_id=f"leg:{i}")

    # 7. synthetic (grounded, template_id known)
    # NOTE: language is DETECTED, not taken from the generator's `lang` field.
    # The generator emits its own codes (en/hi/te/hinglish) which would split the
    # language table into duplicate buckets (e.g. 'en' 2724 next to 'english'
    # 12712) and corrupt every per-language count. Detection gives us one
    # consistent taxonomy.
    p = ROOT / "data/synthetic/synthetic_sms.csv"
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as fh:
            for i, r in enumerate(csv.DictReader(fh)):
                add(r["text"], r["label"], "synthetic", src_id=f"syn:{i}",
                    template_id=r["template_id"], category=r["category"],
                    real=False)

    # 8. synthetic marketing_spam (supplementary, incl. Tenglish)
    p = ROOT / "data/synthetic/synthetic_marketing.csv"
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as fh:
            for i, r in enumerate(csv.DictReader(fh)):
                add(r["text"], "marketing_spam", "synthetic_marketing",
                    src_id=f"mk:{i}", template_id=r["template_id"],
                    category=r["category"], real=False)

    # Human-reviewed, locally redacted SMS export. Unresolved rows are omitted.
    # Labels from the sheet are authoritative; do not run them through the
    # heuristic classifier. The private CSV is ignored by git.
    p = OUT / "mobile_sms_review_classified.csv"
    if p.exists():
        allowed = {"legitimate", "marketing_spam", "scam"}
        seen = {}
        with p.open(encoding="utf-8-sig", newline="") as fh:
            for i, r in enumerate(csv.DictReader(fh)):
                label = (r.get("label") or "").strip().lower()
                text = (r.get("text_redacted") or "").strip()
                if label not in allowed or not text:
                    continue
                key = norm(text)
                if key in seen and seen[key] != label:
                    raise ValueError("Conflicting human labels in mobile SMS review sheet")
                seen[key] = label
                add(text, label, "mobile_sms_review", src_id=f"mobile:{i}",
                    category="user_reviewed_sms")
                rows[-1]["_human_target_label"] = label
                rows[-1]["_human_label_reason"] = "user-reviewed redacted mobile SMS"
        print(f"  loaded {len(seen):,} reviewed mobile SMS templates; unresolved rows skipped")

    return rows


# ---------------------------------------------------------------------------
# Near-duplicate detection: token-set Jaccard over a small sample for speed.
# Near-dupes MUST stay in the same split, otherwise evaluation leaks.
# ---------------------------------------------------------------------------
def tokens(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def build_duplicate_groups(rows, threshold=0.7):
    """Union-find over near-duplicates. Uses char-3gram + word tokens mixed so
    that both exact and 'same message with one entity swapped' are caught."""
    feats = []
    for r in rows:
        t = r["_norm"]
        w = set(re.findall(r"[a-z0-9]+", t))
        c = {t[i:i + 3] for i in range(len(t) - 2)}
        feats.append((w, c))

    parent = list(range(len(rows)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # Bucket by length to avoid full O(n^2). Short messages land in the same
    # buckets by the thousand, so cap per-bucket comparison count -- otherwise a
    # single bucket degenerates into O(n^2) again (this stalled at 30k rows).
    order = sorted(range(len(rows)), key=lambda i: len(rows[i]["_norm"]))
    buckets = defaultdict(list)
    BUCKET = 12
    MAX_PER_BUCKET = 900
    for i in order:
        L = len(rows[i]["_norm"]) // BUCKET
        for b in (L, L + 1):
            cand = buckets[b][-MAX_PER_BUCKET:]
            for j in cand:
                wi, ci = feats[i]
                wj, cj = feats[j]
                if not wi or not wj:
                    continue
                inter = len(wi & wj)
                jac = inter / len(wi | wj)
                if jac >= threshold:
                    ci_inter = len(ci & cj)
                    cjac = ci_inter / max(len(ci | cj), 1)
                    if cjac >= 0.5 or jac >= 0.9:
                        union(i, j)
            buckets[b].append(i)

    groups = defaultdict(list)
    for i in range(len(rows)):
        groups[find(i)].append(i)
    return groups


def load_human_overrides():
    """review_id/text -> adjudicated label from the human annotation pass.

    These take precedence over the regex labeller. Keyed on normalized text so
    the join is independent of source-file column layout.
    """
    p = ROOT / "data/processed/human_overrides.csv"
    if not p.exists():
        print("  (no human_overrides.csv found -- regex labels only)")
        return {}, {}
    with p.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    labels, basis = {}, {}
    for r in rows:
        k = r["text_norm"]
        labels[k] = r["override_label"]
        basis[k] = f"human: {r['decision_kind']} ({r['decision_basis']})"
    print(f"  loaded {len(labels)} human overrides from {p.name}")
    return labels, basis


def main():
    rows = load_sources()
    print(f"loaded {len(rows):,} rows from all sources")

    overrides, override_basis = load_human_overrides()

    # --- label -------------------------------------------------------------
    n_override = 0
    for r in rows:
        lab, reason = classify(r["text"], r["original_label"])
        key = r["_norm"]
        if r.get("_human_target_label"):
            n_override += 1
            r["auto_target_label"] = lab
            r["auto_label_reason"] = reason
            lab = r["_human_target_label"]
            reason = r["_human_label_reason"]
            r["label_source"] = "human_mobile_review"
        elif key in overrides and overrides[key]:
            n_override += 1
            r["auto_target_label"] = lab
            r["auto_label_reason"] = reason
            lab = overrides[key]
            reason = override_basis.get(key, "human adjudication")
            r["label_source"] = "human"
        else:
            r["auto_target_label"] = lab
            r["auto_label_reason"] = reason
            r["label_source"] = "auto"
        r["target_label"] = lab
        r["label_reason"] = reason

    print(f"  human overrides applied: {n_override:,}")

    counts = Counter(r["target_label"] for r in rows)
    print(f"\nTARGET LABEL DISTRIBUTION:")
    for k, v in counts.most_common():
        print(f"  {k:16} {v:>7,}  ({v/len(rows)*100:5.1f}%)")

    # --- review queue ------------------------------------------------------
    review = [r for r in rows if r["target_label"] == "review"]
    print(f"\nreview queue: {len(review):,} rows ({len(review)/len(rows)*100:.1f}%)")
    rc = Counter(r["label_reason"] for r in review)
    for reason, n in rc.most_common():
        print(f"    {n:>6,}  {reason}")

    # --- write labeled corpus ---------------------------------------------
    cols = ["text", "original_label", "target_label", "auto_target_label",
            "auto_label_reason", "label_source", "label_reason", "source",
            "source_id", "template_id", "category", "language", "script",
            "real_or_synthetic"]
    p_all = OUT / "corpus_labeled.csv"
    with p_all.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {p_all.name} ({len(rows):,} rows)")

    p_rev = OUT / "review_queue.csv"
    with p_rev.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(review)
    print(f"wrote {p_rev.name} ({len(review):,} rows)")

    # --- training-ready + duplicate groups ---------------------------------
    trainable = [r for r in rows if r["target_label"] != "review"]
    print(f"\ntrainable (review excluded): {len(trainable):,}")

    groups = build_duplicate_groups(trainable)
    gid = {}
    for gnum, (root, idxs) in enumerate(sorted(groups.items())):
        for i in idxs:
            gid[i] = f"dg{gnum}"
    multi = sum(1 for v in groups.values() if len(v) > 1)
    big = sorted((len(v) for v in groups.values()), reverse=True)[:5]
    print(f"duplicate groups: {len(groups):,} ({multi:,} contain >1 row)")
    print(f"largest group sizes: {big}")
    for i, r in enumerate(trainable):
        r["dup_group"] = gid[i]

    p_tr = OUT / "corpus_train_ready.csv"
    cols2 = cols + ["dup_group"]
    with p_tr.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols2, extrasaction="ignore")
        w.writeheader()
        w.writerows(trainable)
    print(f"wrote {p_tr.name} ({len(trainable):,} rows)")

    # --- counts by class x language x source --------------------------------
    print("\n" + "=" * 72)
    print("CLASS x LANGUAGE")
    print("=" * 72)
    tab = defaultdict(Counter)
    for r in trainable:
        tab[r["language"]][r["target_label"]] += 1
    langs = sorted(tab, key=lambda l: -sum(tab[l].values()))
    print(f"{'language':12} {'legit':>7} {'mkt_spam':>9} {'scam':>7} {'total':>8}")
    for l in langs:
        c = tab[l]
        print(f"  {l:10} {c.get('legitimate',0):>7,} {c.get('marketing_spam',0):>9,} "
              f"{c.get('scam',0):>7,} {sum(c.values()):>8,}")

    print("\n" + "=" * 72)
    print("CLASS x SOURCE")
    print("=" * 72)
    tab2 = defaultdict(Counter)
    for r in trainable:
        tab2[r["source"]][r["target_label"]] += 1
    for s in sorted(tab2, key=lambda s: -sum(tab2[s].values())):
        c = tab2[s]
        print(f"  {s:16} legit {c.get('legitimate',0):>6,}  "
              f"mkt {c.get('marketing_spam',0):>6,}  scam {c.get('scam',0):>6,}")

    print("\n" + "=" * 72)
    print("ADEQUACY CHECK (>=500 per class per language for a defensible claim)")
    print("=" * 72)
    problems = []
    for l in langs:
        c = tab[l]
        n = sum(c.values())
        thin = [k for k in ("legitimate", "marketing_spam", "scam")
                if c.get(k, 0) < 500]
        flag = "OK " if n >= 1500 and not thin else "!! "
        print(f"  {flag}{l:12} total {n:>6,}   thin classes: {thin or 'none'}")
        if thin:
            problems.append((l, thin))
    print("\nVERDICT:")
    if problems:
        print(f"  {len(problems)} language(s) cannot support a per-language claim:")
        for l, thin in problems:
            print(f"    - {l}: thin on {', '.join(thin)}")
    else:
        print("  all languages adequate")


if __name__ == "__main__":
    main()
