"""
Inference layer: loads the artifact, classifies, and produces an honest
explanation.

Response contract consumed by design/index.html:
    confidence   float 0..1  probability of the predicted class
    verdict      'scam' | 'marketing_spam' | 'legitimate'
    signals[]    { label, severity, weight }
    model_version, latency_ms
plus additive fields the current UI does not render yet (language, script,
distractor_keywords) -- ignored by the existing frontend, harmless to add.

EXPLAINABILITY HONESTY
----------------------
`signals` mixes two clearly-labelled sources:
    source='model'  the classifier's own probability contribution
    source='rule'   a narrow, disclosed, high-precision pattern match

The rules are NOT the detector. They exist only for the OTP-share case that
measurement showed is the project's hardest boundary, and every rule hit is
returned to the UI so a user can see and dispute it. An earlier rule layer in
the previous attempt silently altered scores; this one is additive and visible.
"""
import json
import pathlib
import re
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import joblib

import guards as _guards

ART = pathlib.Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = ART / "model.joblib"
META_PATH = ART / "metadata.json"

# ---------------------------------------------------------------------------
# DISTRACTOR KEYWORDS -- the whole point of the hard-negative work.
#
# These words are present in genuine bank alerts as often as in scams, so their
# presence must NOT push a message toward 'scam'. They are reported separately
# so the UI can say "this contains scary words but asks for nothing".
# ---------------------------------------------------------------------------
DISTRACTORS = {
    "OTP": [r"\botp\b", r"ओटीपी", r"ఓటీపీ", r"one\s?time\s?pass"],
    "KYC": [r"\bkyc\b", r"केवाईसी", r"కెవైసీ", r"केवाईसी"],
    "account": [r"\baccount\b", r"खाता", r"ఖాతా", r"a/c\b"],
    "blocked": [r"\bblock(ed)?\b", r"ब्लॉक", r"బ్లాక్", r"restrict", r"freeze",
                r"deactivat", r"सिलेंडर"],
    "verify": [r"\bverif", r"सत्याप", r"ధృవీకర"],
    "security": [r"\bsecurity\b", r"सुरक्षा", r"సురక్ష"],
    "password": [r"\bpassword\b", r"पासवर्ड", r"పాస్‌వర్డ్"],
}

# ---------------------------------------------------------------------------
# HIGH-PRECISION RULES. Each fires only on an explicit DEMAND, never on a bare
# topic noun. Measured before shipping: broad variants (bare 'charge', bare
# 'OTP', bare 'KYC') flagged genuine bank notices and were removed.
#
# GUARDS follow. A rule must not fire when the message PROHIBITS the action or is
# a routine billing notice. Both were measured false positives: a genuine OTP
# says "do not share it with anyone", and a genuine card reminder says
# "Rs 499. Pay now to avoid late fees". Flagging those is worse than flagging
# nothing, because the rule is shown to the reader.
# ---------------------------------------------------------------------------
PROHIBITION = _guards.PROHIBITION
BILLING_CONTEXT = _guards.BILLING_CONTEXT
OFFICIAL_ROUTE = _guards.OFFICIAL_ROUTE

RULES = [
    ("credential_request", "high",
     [r"(share|send|provide|give|forward|bhej|bhejo|bhejein|bheje|bhejiye)"
      r".{0,40}(\botp\b|one\s?time\s?pass|password|cvv|card\s*no)",
      r"(\botp\b|one\s?time\s?pass).{0,40}"
      r"(share|send|provide|bhej|bhejo|bhejein|bheje|bhejiye)"],
     "Asks the reader to send or share an OTP, password or card detail"),

    ("identity_document_request", "high",
     [r"(send|share|provide|upload|bhej|bhejo).{0,40}"
      r"(aadhaar|aadhar|pan\s*(no|number)|आधार|ఆధార్)",
      r"(aadhaar|aadhar|pan\s*(no|number)).{0,50}"
      r"(send|share|provide|upload|bhej|bhejo)"],
     "Asks the reader to send or upload an identity document"),

    ("authority_impersonation", "high",
     [r"(police|cyber\s*cell|cyber\s*crime|crime\s*branch|sit|cbi|"
      r"it\s*police|national\s*cyber|एनसीबी)"
      r".{0,70}(arrest|case|fraud|notice|probe|investigation|warrant|"
      r"compounding|laundering|blackmail|"
      r"गिरफ़्तार|वारंट|मुकदमा|लॉन्ड्रिंग|"
      r"పోలీస్|అరెస్ట్|వారంట్|కేస్)",
      r"(पुलिस|साइबर\s*सेल|सीबीआई|पोलीस్|సైబర్\s*సెల్)"
      r".{0,70}(गिरफ़्तार|वारंट|मुकदमा|लॉन्ड्रिंग|"
      r"అరెస్ట్|వారంట్|కేస్)"],
     "Impersonates a police, cybercrime or government authority"),

    ("payment_demand", "high",
     [r"(transfer|send|wire|pay|bhej|bhejo|bhejein|bheje).{0,50}"
      r"(rs\.?|₹|rupees|lakh|crore|upi|account no|रुपये|रुपए|रूपायलы)",
      r"(rs\.?\s?[\d,]+|₹\s?[\d,]+|\bupi\b).{0,60}"
      r"\b(bhej|bhejo|bhejein|bhejiye|transfer|send|pay)\b",
      r"(भेज|भेजें|भेजिए|जमा).{0,60}(रुपये|रुपए|upi|खाता)",
      r"(పంపండి|చెల్లించండి).{0,60}(రూపాయలు|యుపిఐ|ఖాతా)"],
     "Demands that money be transferred or paid"),

    ("malicious_link", "medium",
     [r"http\S+.*(verify|kyc|update|claim|secure|account|login|otp)",
      r"bit\.ly|tinyurl|t\.co|short\.link|\.tk/|bit\.do",
      r"(download|install).{0,30}(app|ऐप|యాప్).{0,40}(security|सुरक्षा|సురక్ష)"],
     "Contains a shortened or look-alike link, or pushes an app for 'security'"),

    ("deadline_pressure", "medium",
     [r"within\s+\d+\s*(min|hour|hr|day)",
      r"\d+\s*(hours?|hrs?|घंटे|घंटों|గంటల)\s*(में|లో|mein)",
      r"(final|permanent|last)\s*(warning|closure|action)",
      r"(अंतिम|स्थायी)\s*(चेतावनी|बंदी)",
      r"तुरंत.{0,25}(भेज|जमा|अपडेट)"],
     "Applies a deadline or threat of permanent closure"),

    ("prize_with_fee", "medium",
     [r"(won|win|winner|selected|congratulat).{0,60}"
      r"(fee|charge|transfer|pay|processing)",
      r"(\d[\d,]*|रुपये|रूपायलు).{0,30}"
      r"(प्रोसेसिंग\s*फीस|पंजीकरण\s*शुल्क|ప్రాసెసింగ్\s*ఫీజు)"],
     "Offers a prize or gift that requires paying a fee"),
]

COMPILED_RULES = [
    (name, sev, [re.compile(p, re.I) for p in pats], desc)
    for name, sev, pats, desc in RULES
]

# A guard suppresses a rule entirely when the message is the safe case it was
# written to avoid confusing.
_GUARDS = {
    "credential_request": PROHIBITION,
    "identity_document_request": PROHIBITION,
    "payment_demand": BILLING_CONTEXT,
}
DISTRACTOR_COMPILED = [
    (name, [re.compile(p, re.I) for p in pats]) for name, pats in DISTRACTORS.items()
]

PROMO = re.compile(
    r"discount\s+\d+|\d+\s*%\s*off|limited\s+(time|period)|free\s+delivery|"
    r"offer|deal|coupon|voucher|prize\s+draw|lucky\s+draw|sale\s+is|call\s+now|"
    r"subscribe|unsubscri|reply\s+(stop|y|n)|\bpromo\b|छूट|ऑफर|मुफ्त|फ्री|"
    r"తగ్గింపు|ఆఫర్|ఉచిత", re.I)


class Predictor:
    def __init__(self, model_path=MODEL_PATH, meta_path=META_PATH):
        self.model_path = pathlib.Path(model_path)
        self.meta_path = pathlib.Path(meta_path)
        self.model = None
        self.meta = {}
        self.loaded = False
        self.load_error = None
        self._load()

    def _load(self):
        try:
            if not self.model_path.exists():
                raise FileNotFoundError(f"artifact missing: {self.model_path}")
            self.model = joblib.load(self.model_path)
            if self.meta_path.exists():
                self.meta = json.loads(
                    self.meta_path.read_text(encoding="utf-8"))
            self.loaded = True
        except Exception as e:                       # noqa: BLE001
            self.load_error = str(e)
            self.loaded = False

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def detect_language(text):
        s = set()
        for ch in text or "":
            cp = ord(ch)
            for nm, (lo, hi) in (
                ("devanagari", (0x0900, 0x097F)), ("bengali", (0x0980, 0x09FF)),
                ("telugu", (0x0C00, 0x0C7F)), ("tamil", (0x0B80, 0x0BFF)),
                ("kannada", (0x0C80, 0x0CFF)), ("malayalam", (0x0D00, 0x0D7F)),
                ("gujarati", (0x0A80, 0x0AFF)), ("gurmukhi", (0x0A00, 0x0A7F)),
                ("arabic", (0x0600, 0x06FF)), ("latin", (0x0041, 0x024F)),
            ):
                if lo <= cp <= hi:
                    s.add(nm)
        if "devanagari" in s:
            return ("hindi", "devanagari") if "latin" not in s \
                else ("hinglish", "mixed_devanagari_latin")
        if "telugu" in s:
            return ("telugu", "telugu") if "latin" not in s \
                else ("tenglish", "mixed_telugu_latin")
        if "tamil" in s:
            return "tamil", "tamil"
        if "kannada" in s:
            return "kannada", "kannada"
        if "malayalam" in s:
            return "malayalam", "malayalam"
        if "bengali" in s:
            return "bengali", "bengali"
        if "gujarati" in s:
            return "gujarati", "gujarati"
        if "arabic" in s:
            return "urdu", "arabic"
        HIN = {"aap", "aapka", "aapki", "hai", "hain", "karo", "kare", "kripya",
               "turant", "abhi", "nahi", "nhi", "bhejo", "waqt", "jaldi", "pakka",
               "shukriya", "namaste", "paisa", "rupaye", "bilkul", "khatam"}
        TEL = {"nuvvu", "meeku", "garu", "kavali", "undi", "pettu", "petta",
               "aapavu", "raaledu", "nenu", "cheppali", "cheppu", "vanki",
               "vandi", "manchi", "paisalu", "theeyali", "saledu", "block"}
        w = set(re.findall(r"[a-z']+", (text or "").lower()))
        if len(w & TEL) >= 2:
            return "tenglish", "latin"
        if len(w & HIN) >= 2:
            return "hinglish", "latin"
        return "english", "latin"

    @staticmethod
    def matched_rules(text):
        out = []
        for name, sev, pats, desc in COMPILED_RULES:
            guard = _GUARDS.get(name)
            if guard is not None and guard.search(text):
                continue          # safe context: this rule must not fire
            hit = next((p.pattern for p in pats if p.search(text)), None)
            if hit:
                out.append({"name": name, "severity": sev, "desc": desc})
        return out

    @staticmethod
    def distractor_keywords(text):
        return [name for name, pats in DISTRACTOR_COMPILED
                if any(p.search(text) for p in pats)]

    # -- main -------------------------------------------------------------
    def predict(self, text):
        started = time.perf_counter()
        text = (text or "").strip()

        if not text:
            return {
                "verdict": "legitimate", "confidence": 0.0,
                "signals": [{"label": "empty_message", "severity": "neutral",
                             "weight": 0.0, "source": "rule",
                             "description": "No message text supplied."}],
                "model_version": self.meta.get("model_version", "unavailable"),
                "latency_ms": 0.0, "error": "empty_message",
            }

        if not self.loaded:
            return {
                "verdict": None, "confidence": 0.0,
                "signals": [{"label": "model_unavailable",
                             "severity": "neutral", "weight": 0.0,
                             "source": "system",
                             "description": f"Model artifact failed to load: "
                                            f"{self.load_error}"}],
                "model_version": "unavailable", "latency_ms": 0.0,
                "error": "model_unavailable",
            }

        probs = self.model.predict_proba([text])[0]
        classes = list(self.model.classes_)
        idx = int(probs.argmax())
        verdict = classes[idx]
        confidence = float(probs[idx])

        rules = self.matched_rules(text)
        distractors = self.distractor_keywords(text)
        language, script = self.detect_language(text)

        signals = []
        # model contribution
        signals.append({
            "label": f"model_{verdict}",
            "severity": "high" if verdict == "scam"
                        else "medium" if verdict == "marketing_spam"
                        else "protective",
            "weight": round(confidence, 4),
            "source": "model",
            "description": f"Classifier output for the {language} "
                           f"({script}) message.",
        })
        # rule contributions, additive and visible
        n = max(len(rules), 1)
        for i, r in enumerate(rules, 1):
            signals.append({
                "label": r["name"], "severity": r["severity"],
                "weight": round(1.0 / n, 4), "source": "rule",
                "description": r["desc"],
            })

        # a legitimate verdict containing scary words deserves an explicit note
        if verdict == "legitimate" and distractors and not rules:
            signals.append({
                "label": "distractor_keywords_present", "severity": "protective",
                "weight": 0.0, "source": "system",
                "description": "Contains "
                               + ", ".join(distractors)
                               + " but asks for nothing in return, which is the "
                                 "signature of a genuine bank or service alert.",
            })

        if verdict == "marketing_spam" or (not rules and
                                           not re.search(r"(otp|aadhaar|kyc|"
                                                         r"blocked|verify)", text, re.I)):
            if verdict == "marketing_spam":
                signals.append({
                    "label": "promotional_wording", "severity": "medium",
                    "weight": 0.0, "source": "rule",
                    "description": "Bulk promotional phrasing detected; no "
                                   "coercive demand present.",
                })

        latency = round((time.perf_counter() - started) * 1000, 2)

        return {
            "verdict": verdict,
            "confidence": round(confidence, 4),
            "confidence_pct": round(confidence * 100, 2),
            "signals": signals,
            "probabilities": {c: round(float(p), 4) for c, p in zip(classes, probs)},
            "language": language,
            "script": script,
            "distractor_keywords": distractors,
            "rules_fired": [r["name"] for r in rules],
            "model_version": self.meta.get("model_version", "unknown"),
            "latency_ms": latency,
            "evaluation_status": self.meta.get(
                "evaluation_status", "indicative_single_annotator_reviewed"),
        }

    def health(self):
        return {
            "status": "ok" if self.loaded else "degraded",
            "model_loaded": self.loaded,
            "model_version": self.meta.get("model_version", "unknown"),
            "classes": self.meta.get("classes", []),
            "training_rows": self.meta.get("training_rows"),
            "evaluation_status": self.meta.get(
                "evaluation_status", "indicative_single_annotator_reviewed"),
            "error": self.load_error,
        }


# Module-level singleton so the artifact is loaded once at startup.
_PREDICTOR = None


def get_predictor():
    global _PREDICTOR
    if _PREDICTOR is None:
        _PREDICTOR = Predictor()
    return _PREDICTOR
