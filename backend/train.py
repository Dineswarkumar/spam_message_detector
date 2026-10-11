"""
Train the Spam Shield classifier and export a deployable artifact.

MODEL CHOICE -- this decision was reversed by measurement, and the reversal is
the interesting part.
---------------------------------------------------------------------------
Round 1, on the corpus as it stood BEFORE the legitimate hard-negative gap was
closed (grouped, stratified, zero leakage, validation only):

    word-only TF-IDF -> LogReg      macro-F1 88.13   hard-negatives misread 28.5%
    word+char TF-IDF -> LogReg      macro-F1 89.29   hard-negatives misread 26.0%
    char-only  TF-IDF -> LogReg      macro-F1 90.67   hard-negatives misread 19.3%
    word+char TF-IDF -> LinearSVC   macro-F1 89.99   hard-negatives misread  2.0%

LinearSVC shipped. The reason was that 24-point hard-negative gap: word n-grams
latch onto "blocked", "verify", "account" and flag genuine bank alerts, which is
exactly the failure this project exists to fix.

But that gap was not a property of the classifier. It was a property of the
TRAINING DATA. The legitimate side of the KYC and billing families was one
template deep against four scam templates, so the only way to avoid false
scam calls was to distrust word features entirely. The model was compensating
for missing data.

Round 2, after adding 18 legitimate transactional templates and the
completion/billing/prohibition guards (see backend/guards.py), across three
grouped splits:

    word+char TF-IDF -> LogReg      macro-F1 92.51 +/- 2.00   hard-neg miss 1.52%
    char-only  TF-IDF -> LogReg      macro-F1 93.16 +/- 1.07   hard-neg miss 1.19%
    word+char TF-IDF -> LinearSVC   macro-F1 91.61 +/- 3.69   hard-neg miss 1.52%

The hard-negative advantage is GONE -- all three models now miss ~1.5% of hard
negatives. The differentiator evaporated the moment the data gap was closed,
which is the honest conclusion: it was a data problem wearing a model's
clothes.

macro-F1 differences are inside the seed spread, so macro-F1 alone cannot pick
a winner. The decision is made on the axis that does separate them:

    - hard-negative miss rate  char-only lowest (1.19%)
    - stability                char-only tightest spread (+/- 1.07 vs +/- 3.69)
    - failure mode             word n-grams are the documented cause of
                                false scam calls on genuine bank alerts; the
                                char-only model does not have that failure mode
    - honesty of the number    LogisticRegression emits real probabilities
                                natively, so the UI confidence is the model's
                                own, not a sigmoid fitted on top of an SVM

So: char_wb(2,5) TF-IDF -> LogisticRegression. No word features at all.

NOTE ON REPORTING: no accuracy figure is written into metadata.json. The final
score is indicative: 305 messages were labelled by one annotator, who has also
human-reviewed the 78 initial model disagreements. There is no second annotator
or inter-annotator agreement statistic.

Usage:
    python backend/train.py
"""
import json
import pathlib
import re
import sys
from collections import Counter
from datetime import datetime, timezone

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.pipeline import Pipeline

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed"
ART = ROOT / "backend/artifacts"

CLASSES = ["legitimate", "marketing_spam", "scam"]
MODEL_VERSION = "ss-charlr-v3"

# Script ranges, measured rather than declared. Needed at inference so the UI
# can report the detected language honestly.
SCRIPT_RANGES = {
    "devanagari": (0x0900, 0x097F), "bengali": (0x0980, 0x09FF),
    "telugu": (0x0C00, 0x0C7F), "tamil": (0x0B80, 0x0BFF),
    "kannada": (0x0C80, 0x0CFF), "malayalam": (0x0D00, 0x0D7F),
    "gujarati": (0x0A80, 0x0AFF), "gurmukhi": (0x0A00, 0x0A7F),
    "arabic": (0x0600, 0x06FF), "latin": (0x0041, 0x024F),
}
HINGLISH = {
    "aap", "aapka", "aapki", "aapke", "hai", "hain", "karo", "kare", "karein",
    "karna", "kripya", "turant", "abhi", "bilkul", "nahi", "nhi", "mat", "sir",
    "madam", "khatam", "bhejo", "khul", "block", "dena", "dunga", "dungi",
    "waqt", "jaldi", "pakka", "dhyan", "shukriya", "namaste", "accha", "paisa",
    "rupaye", "bharosa",
}
TANGLISH = {
    "nuvvu", "meeku", "garu", "kavali", "undi", "chalundi", "pettu", "petta",
    "aapavu", "raaledu", "nenu", "em", "iki", "kurchi", "vachayi", "theeyali",
    "saledu", "paisalu", "cheppali", "cheppu", "vanki", "vandi", "manchi",
    "sundari", "dhanyaludu", "krupya", "kaani", "aaputha", "band", "block",
    "surakshalu", "ekkadiki", "chesavandi", "pani", "cheyyali",
}


def detect_language(text):
    s = set()
    for ch in text or "":
        cp = ord(ch)
        for name, (lo, hi) in SCRIPT_RANGES.items():
            if lo <= cp <= hi:
                s.add(name)
    non_latin = s - {"latin"}
    if "devanagari" in s:
        return ("hindi", "devanagari") if "latin" not in s else \
               ("hinglish", "mixed_devanagari_latin")
    if "telugu" in s:
        return ("telugu", "telugu") if "latin" not in s else \
               ("tenglish", "mixed_telugu_latin")
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
    words = set(re.findall(r"[a-z']+", (text or "").lower()))
    if len(words & TANGLISH) >= 2:
        return "tenglish", "latin"
    if len(words & HINGLISH) >= 2:
        return "hinglish", "latin"
    return "english", "latin"


def group_key(r):
    if r.get("real_or_synthetic") == "synthetic" or r.get("template_id"):
        return f"tpl::{r['template_id']}"
    return f"dup::{r.get('dup_group')}"


def build_pipeline():
    return Pipeline([
        ("features", TfidfVectorizer(
            analyzer="char_wb", ngram_range=(2, 5), min_df=2,
            max_features=300_000, sublinear_tf=True, lowercase=True)),
        ("clf", LogisticRegression(
            C=4.0, max_iter=2000, class_weight="balanced", random_state=42)),
    ])


def main():
    split_train = DATA / "split_train.csv"
    split_val = DATA / "split_val.csv"
    if not split_train.exists():
        print(f"ERROR: {split_train} not found. Run scripts/model_comparison.py first.")
        sys.exit(1)

    import csv as _csv
    tr = list(_csv.DictReader(split_train.open(encoding="utf-8-sig", newline="")))
    tr = [r for r in tr if r["target_label"] in CLASSES]
    print(f"train rows: {len(tr):,}  {dict(Counter(r['target_label'] for r in tr))}")

    Xtr = [r["text"] for r in tr]
    ytr = [r["target_label"] for r in tr]

    pipe = build_pipeline()
    print("fitting (char_wb(2,5) TF-IDF -> LogisticRegression)...")
    pipe.fit(Xtr, ytr)
    print("done.")

    # ---- validation report (NOT the final number) -------------------------
    val_metrics = None
    if split_val.exists():
        va = list(_csv.DictReader(split_val.open(encoding="utf-8-sig", newline="")))
        va = [r for r in va if r["target_label"] in CLASSES]
        pred = pipe.predict([r["text"] for r in va])
        yv = [r["target_label"] for r in va]
        acc = accuracy_score(yv, pred)
        macro = f1_score(yv, pred, average="macro", labels=CLASSES, zero_division=0)
        print(f"\nVALIDATION (iteration surface, not the final score):")
        print(f"  accuracy {acc*100:.2f}%   macro-F1 {macro*100:.2f}%   n={len(va):,}")
        print(classification_report(yv, pred, labels=CLASSES, digits=4, zero_division=0))
        val_metrics = {"accuracy": round(acc, 4), "macro_f1": round(macro, 4),
                       "n": len(va)}

    # ---- export -----------------------------------------------------------
    ART.mkdir(parents=True, exist_ok=True)
    model_path = ART / "model.joblib"
    joblib.dump(pipe, model_path, compress=3)

    meta = {
        "model_version": MODEL_VERSION,
        "model_type": "LogisticRegression on char_wb(2,5) TF-IDF",
        "classes": CLASSES,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_rows": len(tr),
        "label_distribution": dict(Counter(ytr)),
        "vectorizer": {
            "char": {"analyzer": "char_wb", "ngram_range": [2, 5], "min_df": 2,
                     "max_features": 300000, "sublinear_tf": True},
        },
        "model_selection": {
            "chosen": "char-only TF-IDF -> LogisticRegression",
            "why": "Hard-negative miss rate is the primary axis for this project "
                   "and is now a tie (1.19%-1.52% across candidates), so the old "
                   "justification for shipping LinearSVC no longer holds. "
                   "macro-F1 differences sit inside the seed spread; the choice "
                   "is made on hard-negative miss rate, stability across grouped "
                   "splits, and the absence of the word-n-gram false-scam "
                   "failure mode.",
            "previous_choice": "calibrated LinearSVC on word+char TF-IDF",
            "previous_choice_invalidated_because": "its 24-point hard-negative "
                   "advantage was caused by missing legitimate training data, "
                   "not by the classifier. Closing that data gap removed the "
                   "advantage entirely.",
            "seed_stability_macro_f1": {
                "word+char_LR": "92.51 +/- 2.00",
                "char_only_LR": "93.16 +/- 1.07",
                "word+char_SVC": "91.61 +/- 3.69",
            },
            "seed_stability_hard_neg_miss": {
                "word+char_LR": "1.52%",
                "char_only_LR": "1.19%",
                "word+char_SVC": "1.52%",
            },
        },
        "validation_metrics": val_metrics,
        "evaluation_status": "indicative_single_annotator_reviewed",
        "evaluation_note": (
            "The published score is indicative: 305 messages were labelled "
            "by one annotator, who also human-reviewed the 78 initial model "
            "disagreements. There is no second annotator or agreement statistic; "
            "the score remains against the original labels."
        ),
        "known_limitations": [
            "Tenglish and Hindi support is synthetic-only and unaudited by a "
            "native speaker.",
            "Roughly 6% of the labelled corpus sits in a review queue and is "
            "excluded from training.",
            "marketing_spam vs scam is a judgement boundary, not a crisp fact.",
            "Validation accuracy on the pure-Devanagari and pure-Telugu slices "
            "is near chance. Those scripts have too few rows to support a "
            "per-language claim; see the ADEQUACY CHECK in the corpus build log.",
            "macro-F1 differences between the top two candidate models are "
            "inside the seed spread, so the shipping choice rests on the "
            "hard-negative axis and on stability, not on macro-F1.",
        ],
        "privacy": "Message bodies are processed in memory and never written to "
                   "disk or application logs.",
    }
    (ART / "metadata.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    size_mb = model_path.stat().st_size / 1024 / 1024
    print(f"\nwrote {model_path}  ({size_mb:.1f} MB)")
    print(f"wrote {ART/'metadata.json'}")
    print(f"\nRender note: artifact is {size_mb:.1f} MB. It must be committed to the "
          f"repo or\nfetched at build time; free instances also sleep, so the first "
          f"request is slow.")


if __name__ == "__main__":
    main()
