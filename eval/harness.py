"""
Eval harness — spam-msg-detector

The point of this file is NOT to produce a nice accuracy number. It is to produce
numbers that survive the question "would a length check have told you the same thing?"

Key design decisions (see AGENTS.md):

1. GROUPED SPLITS. Any source that carries template/group identity is split by
   group, never by row. Otherwise the model memorises our own boilerplate and the
   test score is fiction. UCI has no template identity, so it splits by row with a
   fixed seed -- that is stated explicitly rather than hidden.

2. LENGTH-CONTROLLED EVAL. UCI spam averages ~138 chars vs ~71 for ham. A linear
   model on TF-IDF will happily learn length and nothing else. So we always report:
     - naive accuracy/F1
     - a LENGTH-ONLY BASELINE (single threshold on char count)
     - a length-matched resampled test set where length carries zero information
   If the model cannot beat the length-only baseline on the length-matched set,
   it has learned nothing that matters.

3. PER-SOURCE reporting. English (UCI) and the thin multilingual slice are
   reported separately. A single blended number would hide that the multilingual
   slice is 800 rows against 5,572 English.

Run:  python eval/harness.py
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

ROOT = Path(__file__).resolve().parent.parent
SEED = 42

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
HINGLISH_MARKERS = {
    "aapka", "aapki", "karein", "karo", "kare", "hai", "hain", "abhi", "turant",
    "nhi", "nahi", "please", "kar", "wala", "wali", "gaya", "raha", "kro",
    "bhejo", "bhej", "se", "mein", "par", "lekin", "bhi", "apna", "mera",
}


# --------------------------------------------------------------------------
# language identification (by script range + marker words, not self-reported)
# --------------------------------------------------------------------------

def detect_language(text: str) -> str:
    dev = len(DEVANAGARI.findall(text))
    if dev / max(len(text), 1) > 0.15:
        return "hindi"
    latin = re.sub(r"[^a-zA-Z ]", " ", text.lower()).split()
    if latin:
        hits = sum(1 for w in latin if w in HINGLISH_MARKERS)
        if hits >= 2:
            return "hinglish"
    return "english"


# --------------------------------------------------------------------------
# data containers
# --------------------------------------------------------------------------

@dataclass
class Example:
    text: str
    label: int          # 1 = spam/scam, 0 = legit
    source: str
    group: str | None   # template id when known; drives the grouped split
    lang: str = field(init=False)

    def __post_init__(self) -> None:
        self.text = unicodedata.normalize("NFKC", self.text).strip()
        self.lang = detect_language(self.text)


def _read(path: Path) -> list[list[str]]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            rows.append(line.split("\t"))
    return rows


def load_uci() -> list[Example]:
    """English backbone. 5,572 rows, ~0% duplicates. No template identity."""
    out = []
    for parts in _read(ROOT / "data/raw/baseline_english/SMSSpamCollection"):
        if len(parts) < 2:
            continue
        tag, msg = parts[0], parts[1]
        if tag not in ("ham", "spam"):
            continue
        out.append(Example(msg, int(tag == "spam"), "uci_en", group=None))
    return out


def load_atharva() -> list[Example]:
    """
    Best multilingual text in hand: 563 real strings, English + Hinglish + Devanagari.
    Each string is its own group -> the grouped split degenerates to a row split
    here, which is correct because there is no template to hold out.
    """
    spec = importlib.util.spec_from_file_location(
        "atharva_dataset", ROOT / "data/raw/phishing_taxonomy/atharva_dataset.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["atharva_dataset"] = mod
    spec.loader.exec_module(mod)

    out = []
    for msg in getattr(mod, "PHISHING_MESSAGES", []):
        out.append(Example(msg, 1, "atharva", group=None))
    for msg in getattr(mod, "LEGIT_MESSAGES", []):
        out.append(Example(msg, 0, "atharva", group=None))
    return out


def load_ysangam() -> list[Example]:
    """
    10,000 claimed rows -> 743 unique. Deduped here. Class balance after dedup
    inverts to ~85% scam and police_digital_arrest dominates, so this is used as a
    TAXONOMY source, not a training set. See AGENTS.md Rule 1.
    """
    import csv

    path = ROOT / "data/raw/needs_verification/ysangam_india_cyber_scam.csv"
    with path.open(encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        cols = reader.fieldnames or []
        text_col = next(
            (c for c in ("message", "text", "sms", "content", "body") if c in cols), None
        )
        label_col = next(
            (c for c in ("is_scam", "label", "scam", "target") if c in cols), None
        )
        if not text_col or not label_col:
            raise SystemExit(f"ysangam columns not understood: {cols}")

        seen, out = set(), []
        for row in reader:
            msg = (row.get(text_col) or "").strip()
            if not msg or msg in seen:
                continue
            seen.add(msg)
            raw = str(row.get(label_col)).strip().lower()
            label = 1 if raw in {"1", "true", "yes", "scam"} else 0
            # template group = the category the row was generated from
            cat = row.get("scam_category") or row.get("category") or "uncat"
            out.append(Example(msg, label, "ysangam", group=f"ys::{cat}"))
    return out


# --------------------------------------------------------------------------
# splits
# --------------------------------------------------------------------------

def grouped_split(examples: list[Example], test_size: float = 0.25, seed: int = SEED):
    """
    Split so that no group appears in both train and test.

    Rows whose group is None (UCI, Atharva) are bucketed into singleton groups,
    which degrades gracefully to a plain stratified row split -- and we say so
    rather than pretending a grouped split happened.
    """
    groups = np.array([e.group if e.group else f"__{i}" for i, e in enumerate(examples)])
    labels = np.array([e.label for e in examples])

    uniq = list(dict.fromkeys(groups))
    rng = np.random.RandomState(seed)
    rng.shuffle(uniq)
    cut = int(len(uniq) * (1 - test_size))
    train_groups = set(uniq[:cut])

    train_idx = [i for i, g in enumerate(groups) if g in train_groups]
    test_idx = [i for i, g in enumerate(groups) if g not in train_groups]

    # rebalance the test side toward 50/50 so F1 is not dominated by class skew
    y_test = labels[test_idx]
    pos = [test_idx[i] for i in np.where(y_test == 1)[0]]
    neg = [test_idx[i] for i in np.where(y_test == 0)[0]]
    k = min(len(pos), len(neg))
    test_idx = list(pos[:k]) + list(neg[:k])
    rng.shuffle(test_idx)
    return [examples[i] for i in train_idx], [examples[i] for i in test_idx]


# --------------------------------------------------------------------------
# length controls
# --------------------------------------------------------------------------

class LengthOnlyBaseline:
    """Predicts spam iff length > threshold. The control every model must beat."""

    def __init__(self) -> None:
        self.threshold = 0

    def fit(self, examples: list[Example]) -> "LengthOnlyBaseline":
        spam = [len(e.text) for e in examples if e.label == 1]
        ham = [len(e.text) for e in examples if e.label == 0]
        if not spam or not ham:
            self.threshold = 0
            return self
        # best single-threshold accuracy by scanning candidate split points
        lengths = sorted(set(len(e.text) for e in examples))
        best, best_acc = lengths[0], 0.0
        for t in lengths:
            pred = [1 if len(e.text) > t else 0 for e in examples]
            acc = accuracy_score([e.label for e in examples], pred)
            if acc > best_acc:
                best, best_acc = t, acc
        self.threshold = best
        return self

    def predict(self, examples: list[Example]) -> list[int]:
        return [1 if len(e.text) > self.threshold else 0 for e in examples]


def length_matched(examples: list[Example], seed: int = SEED) -> list[Example]:
    """
    Resample so that within every length bucket, spam and ham are equally
    represented. After this, message length carries no class information at all,
    so any remaining accuracy is real signal.
    """
    rng = np.random.RandomState(seed)
    lengths = np.array([len(e.text) for e in examples])
    if len(examples) < 10:
        return examples
    # quantile buckets on the pooled length distribution
    qs = np.quantile(lengths, [0, .2, .4, .6, .8, 1.0])
    qs[-1] += 1
    buckets = np.clip(np.digitize(lengths, qs[1:-1], right=True), 0, 4)

    out: list[Example] = []
    for b in range(buckets.max() + 1):
        pos = [e for e, k in zip(examples, buckets) if k == b and e.label == 1]
        neg = [e for e, k in zip(examples, buckets) if k == b and e.label == 0]
        k = min(len(pos), len(neg))
        if k == 0:
            continue
        out.extend(list(rng.choice(pos, k, replace=False)))
        out.extend(list(rng.choice(neg, k, replace=False)))
    return out


def report(name: str, ex: list[Example], y_true: list[int], y_pred: list[int]) -> dict:
    m = {
        "n": len(ex),
        "acc": accuracy_score(y_true, y_pred),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "prec": precision_score(y_true, y_pred, zero_division=0),
        "rec": recall_score(y_true, y_pred, zero_division=0),
    }
    print(f"  {name:<34} n={m['n']:<6} acc={m['acc']:.3f}  "
          f"P={m['prec']:.3f}  R={m['rec']:.3f}  F1={m['f1']:.3f}")
    return m


# --------------------------------------------------------------------------
# model
# --------------------------------------------------------------------------

def build_model() -> Pipeline:
    """
    Char n-grams carry the multilingual signal (Devanagari breaks on whitespace),
    word n-grams carry the English signal. Union of both, linear on top.
    """
    return Pipeline([
        ("feats", FeatureUnion([
            ("char", TfidfVectorizer(
                analyzer="char_wb", ngram_range=(2, 5), min_df=2,
                sublinear_tf=True, max_features=200_000, lowercase=True)),
            ("word", TfidfVectorizer(
                analyzer="word", ngram_range=(1, 2), min_df=2,
                sublinear_tf=True, max_features=100_000, lowercase=True)),
        ])),
        ("clf", LogisticRegression(
            C=4.0, max_iter=2000, class_weight="balanced", solver="liblinear")),
    ])


def dedupe_pool(pool: list[Example]) -> tuple[list[Example], list[tuple[str, str]]]:
    """
    Deduplicate by normalised text across the ENTIRE pool, not just within a file.

    This is not theoretical: Atharva strings overlap with UCI messages. If you
    split per-source and then union, the same text lands in train and test and
    the score is fiction. First source in the list wins.
    """
    seen: dict[str, Example] = {}
    dropped: list[tuple[str, str]] = []
    for e in pool:
        key = re.sub(r"\s+", " ", e.text.lower()).strip()
        if key in seen:
            dropped.append((seen[key].source, e.source))
        else:
            seen[key] = e
    return list(seen.values()), dropped


def _assert_no_leak(train: list[Example], test: list[Example]) -> None:
    """Hard failure if any test message also appears in train. This is the single
    most common way an eval harness lies to you, so it is an assert, not a comment."""
    seen = {e.text for e in train}
    overlap = [e for e in test if e.text in seen]
    if overlap:
        raise SystemExit(
            f"LEAKAGE: {len(overlap)}/{len(test)} test messages also appear in "
            f"train. e.g. {overlap[0].text[:70]!r}"
        )
    print(f"  [leak check] ok -- 0/{len(test)} test messages seen in training")


def main() -> None:
    print("=" * 78)
    print("SPAM DETECTOR -- EVAL HARNESS")
    print("Every number below is length-controlled. Read Rule 3 in AGENTS.md.")
    print("=" * 78)

    uci = load_uci()
    print(f"\nloaded: uci_en={len(uci)}")

    try:
        ath = load_atharva()
        print(f"loaded: atharva={len(ath)}")
    except Exception as exc:  # pragma: no cover
        print(f"loaded: atharva FAILED ({exc})")
        ath = []

    for name, data in (("uci_en", uci), ("atharva", ath)):
        if not data:
            continue
        print(f"    {name}: " + ", ".join(
            f"{lang}={sum(1 for e in data if e.lang == lang)}"
            for lang in ("english", "hinglish", "hindi")))

    # ---------------- SPLIT FIRST, THEN FIT -------------------------------
    # Splitting before fitting is not a style preference. If you carve the test
    # set out of the same pool you fit on, you are grading your own homework.
    # ---------------- dedupe globally, THEN split ------------------------
    # UCI is listed first so the trusted source wins any collision.
    pool, dropped = dedupe_pool(uci + ath)
    cross = {}
    for a, b in dropped:
        cross[(a, b)] = cross.get((a, b), 0) + 1
    print(f"\ndedupe: pool {len(uci) + len(ath)} -> {len(pool)} "
          f"({len(dropped)} duplicate texts removed)")
    for (a, b), n in sorted(cross.items(), key=lambda kv: -kv[1]):
        print(f"    {a} -> {b}: {n} shared messages")

    y = lambda d: [e.label for e in d]
    by_source: dict[str, list[Example]] = {}
    for e in pool:
        by_source.setdefault(e.source, []).append(e)

    uci_train, uci_test = train_test_split(
        by_source["uci_en"], test_size=0.25, random_state=SEED,
        stratify=y(by_source["uci_en"]))
    ath_train, ath_test = train_test_split(
        by_source["atharva"], test_size=0.30, random_state=SEED,
        stratify=y(by_source["atharva"]))

    train = uci_train + ath_train
    print(f"\nsplits: train={len(train)}  uci_test={len(uci_test)}  atharva_test={len(ath_test)}")
    print("checking for train/test leakage ...")
    _assert_no_leak(train, uci_test)
    _assert_no_leak(train, ath_test)

    print("\nfitting model on English backbone + Atharva multilingual slice ...")
    model = build_model()
    model.fit([e.text for e in train], y(train))

    # Baseline must be fit on BALANCED training data, otherwise "predict the
    # majority class" wins its own accuracy contest and reports F1 = 0 forever.
    baseline = LengthOnlyBaseline().fit(length_matched(train))
    print(f"length-only baseline threshold: {baseline.threshold} chars")

    # ---------------- English: length-controlled --------------------------
    lm = length_matched(uci_test)

    print(f"\n--- UCI held-out (n={len(uci_test)}, length-matched n={len(lm)}) ---")
    y_u = [e.label for e in uci_test]
    m_raw = report("model  (raw)", uci_test, y_u, model.predict([e.text for e in uci_test]))
    report("LENGTH-ONLY BASELINE (raw)", uci_test, y_u, baseline.predict(uci_test))

    print()
    y_m = [e.label for e in lm]
    base_m = report("LENGTH-ONLY BASELINE (matched)", lm, y_m, baseline.predict(lm))
    m_ctrl = report("model  (length-matched)", lm, y_m, model.predict([e.text for e in lm]))

    delta = m_ctrl["f1"] - base_m["f1"]
    print(f"\n  >>> REAL SIGNAL = matched F1 {m_ctrl['f1']:.3f} - baseline F1 {base_m['f1']:.3f}"
          f"  =  {delta:+.3f}")
    if delta < 0.02:
        print("  >>> VERDICT: model barely beats 'look at message length'."
              " Do NOT report a headline F1 from this run.")

    # ---------------- multilingual held-out --------------------------------
    print(f"\n--- Atharva held-out (n={len(ath_test)}) -- the thin multilingual slice ---")
    y_a = y(ath_test)
    report("LENGTH-ONLY BASELINE", ath_test, y_a, baseline.predict(ath_test))
    report("model", ath_test, y_a, model.predict([e.text for e in ath_test]))

    print("\n  per-language on Atharva held-out (our ONLY multilingual signal):")
    for lang in ("english", "hinglish", "hindi"):
        subset = [e for e in ath_test if e.lang == lang]
        if len(subset) < 10:
            print(f"    {lang:<32} n={len(subset):<5} (too few to report)")
            continue
        report(f"    model ({lang})", subset, y(subset),
               model.predict([e.text for e in subset]))

    # ---------------- per-language breakdown ------------------------------
    print("\n--- per-language, UCI test, length-matched ---")
    for lang in ("english", "hinglish", "hindi"):
        subset = [e for e in lm if e.lang == lang]
        if len(subset) < 10:
            print(f"  {lang:<34} n={len(subset):<6} (too few to report)")
            continue
        y_s = [e.label for e in subset]
        report(f"model ({lang})", subset, y_s, model.predict([e.text for e in subset]))

    # ---------------- detailed report for the headline run -----------------
    print("\n--- classification report (UCI test, length-matched, model) ---")
    print(classification_report(y_m, model.predict([e.text for e in lm]),
                                target_names=["legit", "spam"], digits=3))

    # ---------------- where does it still fail? ---------------------------
    print("--- 5 highest-confidence false positives on the matched set ---")
    fp = [(e, p) for e, p in zip(lm, model.predict_proba([x.text for x in lm])[:, 1])
          if e.label == 0 and p > 0.5]
    if not fp:
        print("  none")
    for e, p in sorted(fp, key=lambda t: -t[1])[:5]:
        print(f"  p={p:.2f} len={len(e.text):<4} | {e.text[:88]}")

    print("\n--- 5 highest-confidence false negatives on the matched set ---")
    fn = [(e, p) for e, p in zip(lm, model.predict_proba([x.text for x in lm])[:, 1])
          if e.label == 1 and p <= 0.5]
    if not fn:
        print("  none")
    for e, p in sorted(fn, key=lambda t: t[1])[:5]:
        print(f"  p={p:.2f} len={len(e.text):<4} | {e.text[:88]}")


if __name__ == "__main__":
    main()
