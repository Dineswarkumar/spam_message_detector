"""Probe: how does the shipped model handle SHORT code-mixed scam messages?

Motivated by a live check where
    "OTP hai 482910. Humare agent ko share karein for verification."
came back marketing_spam at 0.48 confidence instead of scam.

Short messages are the known blind spot of char n-gram models: with only ~8
tokens there are too few character n-grams to separate two texts that share
vocabulary. This measures whether that is a one-off or a systematic slice.

Validation only. Nothing here touches the holdout.
"""
import csv
import importlib.util
import pathlib
import sys
from collections import Counter, defaultdict

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


def main():
    import joblib
    pipe = joblib.load(ROOT / "backend/artifacts/model.joblib")

    val = list(csv.DictReader((P / "split_val.csv").open(encoding="utf-8-sig", newline="")))
    X = [r["text"] for r in val]
    y = [r["target_label"] for r in val]
    pred = pipe.predict(X)
    proba = pipe.predict_proba(X)
    classes = list(pipe.named_steps["clf"].classes_)
    scam_idx = classes.index("scam")

    print(f"val rows: {len(val):,}")

    # ---- how much does text length decide the outcome? --------------------
    buckets = defaultdict(lambda: {"n": 0, "scam_recall": 0, "leaked_to_mkt": 0})
    for r, p in zip(val, pred):
        L = len(r["text"])
        b = "<=60" if L <= 60 else ("61-100" if L <= 100 else ("101-160" if L <= 160 else ">160"))
        buckets[b]["n"] += 1
        if r["target_label"] == "scam":
            if p == "scam":
                buckets[b]["scam_recall"] += 1
            elif p == "marketing_spam":
                buckets[b]["leaked_to_mkt"] += 1

    print("\nSCAM RECALL BY MESSAGE LENGTH")
    print(f"  {'len':>9} {'scam n':>8} {'recall%':>8} {'->mkt':>7} {'leak%':>7}")
    for b in ("<=60", "61-100", "101-160", ">160"):
        d = buckets[b]
        n = d["scam_recall"] + d["leaked_to_mkt"]
        if not n:
            continue
        print(f"  {b:>9} {n:>8} {d['scam_recall']/n*100:>7.1f}% {d['leaked_to_mkt']:>7}"
              f" {d['leaked_to_mkt']/n*100:>6.1f}%")

    # ---- confidence on the known-hard short OTP-share cases ---------------
    print("\nPROBE MESSAGES (short, code-mixed, credential request):")
    probes = [
        ("hi ", "OTP hai 482910. Humare agent ko share karein for verification."),
        ("hi ", "आपके डेबिट कार्ड से विदेश में ट्रांजैक्शन हुआ है। ब्लॉक करने के लिए OTP भेजें।"),
        ("te ", "మీ OTP ఇవ్వండి. వెంటనే."),
        ("en ", "Share OTP 482910 with agent to verify."),
        ("en ", "Send your Aadhaar and OTP to this number now."),
    ]
    for lang, t in probes:
        pr = pipe.predict([t])[0]
        conf = float(pipe.predict_proba([t])[0][scam_idx])
        print(f"  [{lang}] pred={pr:<16} P(scam)={conf:.3f}  {t[:62]}")

    # ---- the actual failures on val ---------------------------------------
    bad = [(r, p, float(pr[scam_idx]))
           for r, p, pr in zip(val, pred, proba)
           if r["target_label"] == "scam" and p != "scam"]
    print(f"\nVAL scam rows NOT predicted scam: {len(bad)} "
          f"({len(bad)/sum(1 for r in val if r['target_label']=='scam')*100:.1f}% of scam)")
    by_pred = Counter(p for _r, p, _c in bad)
    print(f"  went to: {dict(by_pred)}")
    print("\n  worst 10 by P(scam):")
    for r, p, c in sorted(bad, key=lambda x: x[2])[:10]:
        print(f"    P(scam)={c:.3f} -> {p:<16} lang={r.get('language',''):<9} "
              f"tpl={r.get('template_id','') or '-':<6} {r['text'][:70]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())