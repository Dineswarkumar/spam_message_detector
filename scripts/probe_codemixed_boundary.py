"""
Decisive comparison: the code-mixed SHORT-scam slice, across all candidates.

WHY
---
The shipped char-only model got a short Hinglish OTP-share scam wrong
("OTP hai 482910. Humare agent ko share karein for verification." ->
marketing_spam, P(scam)=0.35). If dropping word features costs recall on
short code-mixed scams, that is the exact failure this project exists to
prevent, and it would outweigh the macro-F1 and stability gains.

So this measures the slice directly rather than arguing from aggregate scores:
for every candidate model, scam recall on short code-mixed validation rows,
and legitimate recall on the matching short hard negatives.

Validation only.
"""
import csv
import importlib.util
import pathlib
import sys
from collections import defaultdict

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mc = load("mc", ROOT / "scripts/model_comparison.py")

CANDIDATES = ["1_word+char_LR", "3_char_only_LR", "4_word+char_SVC"]
SHORT = 110          # chars -- "one SMS screen"
CODEMIX = {"hinglish", "tenglish", "telugu", "hindi"}


def main():
    rows = list(csv.DictReader(
        (P / "corpus_train_ready.csv").open(encoding="utf-8-sig", newline="")))
    rows = [r for r in rows if r["target_label"] in mc.CLASSES]
    _tr, val, _te = mc.three_way_grouped_split(rows, seed=42)

    short_mix_scam = [r for r in val
                      if r["target_label"] == "scam"
                      and r.get("language") in CODEMIX
                      and len(r["text"]) <= SHORT]
    short_mix_legit = [r for r in val
                       if r["target_label"] == "legitimate"
                       and r.get("language") in CODEMIX
                       and len(r["text"]) <= SHORT
                       and mc.SCARY.search(r["text"])]

    print(f"short (<= {SHORT} chars) code-mixed SCAM rows in val : {len(short_mix_scam)}")
    print(f"short code-mixed HARD NEGATIVES in val             : {len(short_mix_legit)}\n")

    models = mc.build_models()
    Xtr = [r["text"] for r in _tr]
    ytr = [r["target_label"] for r in _tr]

    print(f"  {'model':18} {'scam recall':>13} {'legit recall':>13} {'both%':>8}")
    print("  " + "-" * 56)
    for cand in CANDIDATES:
        m = models[cand]
        m.fit(Xtr, ytr)
        ps = m.predict([r["text"] for r in short_mix_scam]) if short_mix_scam else []
        pl = m.predict([r["text"] for r in short_mix_legit]) if short_mix_legit else []
        sr = sum(1 for p in ps if p == "scam") / len(ps) * 100 if len(ps) else float("nan")
        lr = sum(1 for p in pl if p != "scam") / len(pl) * 100 if len(pl) else float("nan")
        both = (sum(1 for p in ps if p == "scam") + sum(1 for p in pl if p != "scam")) \
            / (len(ps) + len(pl)) * 100 if (len(ps) + len(pl)) else float("nan")
        print(f"  {cand:18} {sr:>12.1f}% {lr:>12.1f}% {both:>7.1f}%")

    print("\n  scam recall = true scam read as scam (want HIGH)")
    print("  legit recall = genuine hard negative NOT read as scam (want HIGH)")

    # the specific message that regressed
    print("\nSPECIFIC REGRESSION MESSAGE, per candidate:")
    t = "OTP hai 482910. Humare agent ko share karein for verification."
    for cand in CANDIDATES:
        m = models[cand]
        m.fit(Xtr, ytr)
        p = m.predict([t])[0]
        print(f"  {cand:18} -> {p}")

    return 0


if __name__ == "__main__":
    sys.exit(main())