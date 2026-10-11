"""
Score the shipped artifact against the hand-labelled final test set.

This is the ONE script allowed to print an accuracy number for this project.

HONESTY RULES ENFORCED HERE
---------------------------
1. Refuses to score if ANY holdout text is present in the training corpus. If
   the corpus was rebuilt and the holdout leaked, the score is fiction.

2. `review` rows are excluded, never counted as correct and never counted as
   wrong. They are reported separately as coverage. Dropping them inflates the
   score slightly, so the excluded count is printed next to the number.

3. Rows flagged as internally inconsistent are NOT silently corrected. The
   score is reported twice: once as annotated, once with the flagged rows
   removed. If the two differ a lot, the label quality is the weak link and
   that should be visible rather than hidden.

4. Every headline number is length-controlled. Spam averages ~138 chars and ham
   ~71, so a model can score well on length alone (AGENTS.md Rule 3).

5. The annotator provenance is printed in the output and carried into the UI.
   Single-annotator means there is no kappa and the number only measures
   agreement with that one person's judgement.

Usage:
    python scripts/score_final_test.py
"""
import csv
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import joblib

ROOT = pathlib.Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"

SHEET = P / "final_test_blinded_excel.csv"
CLEAN = P / "final_test_annotator_A.csv"
ART = ROOT / "backend/artifacts/model.joblib"
REPORT = P / "final_score_report.json"

VALID = ["legitimate", "marketing_spam", "scam"]

# Rows the consistency checker found carrying two different labels for the same
# template. Left EXACTLY as the annotator wrote them.
KNOWN_INCONSISTENT = {"FT0031", "FT0003"}

SCARY = re.compile(
    r"otp|kyc|verify|block|suspend|account|freeze|restrict|pending|expire|"
    r"ओटीपी|केवाईसी|ఓటీపీ|కెవైసీ", re.I)


def norm(t):
    return " ".join((t or "").lower().split())


def detect_language(text):
    """Script/language detection, borrowed from backend/train.py so the score
    breakdown uses the same logic the deployed predictor does."""
    sys.path.insert(0, str(ROOT / "backend"))
    import importlib.util as _il
    spec = _il.spec_from_file_location(
        "_tr", ROOT / "backend/train.py")
    # train.py has a main() guarded by __main__, so importing it is safe.
    tr = _il.module_from_spec(spec)
    spec.loader.exec_module(tr)
    return tr.detect_language(text)


def load(p):
    return list(csv.DictReader(pathlib.Path(p).open(encoding="utf-8-sig", newline="")))


def prf(y, p, labels):
    out = {}
    for lab in labels:
        tp = sum(1 for a, b in zip(y, p) if a == lab and b == lab)
        fp = sum(1 for a, b in zip(y, p) if a != lab and b == lab)
        fn = sum(1 for a, b in zip(y, p) if a == lab and b != lab)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out[lab] = {"precision": prec, "recall": rec, "f1": f1,
                    "support": sum(1 for a in y if a == lab)}
    return out


def score(rows, pipe):
    X = [r["text"] for r in rows]
    y = [r["final_label"] for r in rows]
    pred = list(pipe.predict(X))
    acc = sum(1 for a, b in zip(y, pred) if a == b) / len(y) * 100
    per = prf(y, pred, VALID)
    macro = sum(per[l]["f1"] for l in VALID) / len(VALID) * 100
    return acc, macro, per, pred


def main():
    pipe = joblib.load(ART)
    raw = load(SHEET)

    # ---- normalise the label vocabulary ---------------------------------
    # Confirmed with the annotator: the four `spam` rows meant `scam`.
    # `review` is the project's own undecidable class and is kept as-is.
    ALIAS = {"spam": "scam", "spam ": "scam", " fraud": "scam",
             "legit": "legitimate", "marketing": "marketing_spam"}
    fixed = 0
    rows = []
    for r in raw:
        lab = (r.get("final_label") or "").strip().lower()
        new = ALIAS.get(lab, lab)
        if new != lab and new in VALID:
            fixed += 1
        rows.append({"sample_id": r["sample_id"], "text": r["text"],
                     "final_label": new, "reason": r.get("reason", ""),
                     "label_as_written": (r.get("final_label") or "").strip()})

    print("=" * 74)
    print("FINAL TEST SET SCORE")
    print("=" * 74)
    print(f"sheet: {SHEET.name}   rows={len(rows)}")
    print(f"labels normalised to the 3-class vocabulary: {fixed}")

    with CLEAN.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["sample_id", "text", "final_label",
                                           "reason", "label_as_written"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote clean annotator-A sheet: {CLEAN.name}")

    # ---- refuse to score on a leaked holdout -----------------------------
    train = load(P / "corpus_train_ready.csv")
    train_texts = {norm(r["text"]) for r in train}
    leaked = [r["sample_id"] for r in rows if norm(r["text"]) in train_texts]
    print(f"\nholdout leakage check: {len(leaked)} of {len(rows)} rows found in "
          f"the training corpus")
    if leaked:
        print("  !! ABORTING. Run scripts/reserve_holdout.py and retrain.")
        for i in leaked[:10]:
            print(f"     {i}")
        return 1
    print("  PASS: every scored row is unseen by the model.")

    scored = [r for r in rows if r["final_label"] in VALID]
    excluded = [r for r in rows if r["final_label"] not in VALID]
    print(f"\nscored rows     : {len(scored)}")
    print(f"excluded 'review': {len(excluded)}  (undecidable, counted neither way)")
    for r in excluded:
        print(f"    {r['sample_id']}  {r['text'][:70]}")

    # ---- headline ---------------------------------------------------------
    acc, macro, per, pred = score(scored, pipe)
    report = {
        "annotator_provenance": "single annotator, no inter-annotator agreement",
        "kappa": None,
        "note": "The test set was sampled from the review queue (rows the "
                "corpus labeller abstained on), stratified by source and script. "
                "It is deliberately harder than the validation split and is NOT "
                "a like-for-like comparison with the validation macro-F1.",
    }
    print(f"\n{'='*74}\nHEADLINE  (all labelled rows, as annotated)\n{'='*74}")
    print(f"  accuracy  {acc:6.2f}%   macro-F1 {macro:6.2f}%   n={len(scored)}")
    print(f"  {'class':16} {'prec':>7} {'rec':>7} {'f1':>7} {'support':>8}")
    for l in VALID:
        d = per[l]
        print(f"  {l:16} {d['precision']*100:6.1f}% {d['recall']*100:6.1f}% "
              f"{d['f1']*100:6.1f}% {d['support']:>8}")

    # confusion
    print(f"\n  confusion (rows = annotator):")
    print(f"    {'':<16}" + "".join(f"{c:>16}" for c in VALID))
    for true_l in VALID:
        cells = ""
        for pred_l in VALID:
            cells += f"{sum(1 for a, b in zip([r['final_label'] for r in scored], pred) if a == true_l and b == pred_l):>16}"
        print(f"    {true_l:<16}{cells}")

    # ---- length-controlled (Rule 3) ---------------------------------------
    print(f"\n{'='*74}\nLENGTH-CONTROLLED  (Rule 3: a model can score well on length alone)")
    print(f"{'='*74}")
    buckets = defaultdict(lambda: {"n": 0, "ok": 0})
    for r, p in zip(scored, pred):
        L = len(r["text"])
        b = "<=60" if L <= 60 else ("61-100" if L <= 100 else
                                    ("101-160" if L <= 160 else ">160"))
        buckets[b]["n"] += 1
        buckets[b]["ok"] += (r["final_label"] == p)
    for b in ("<=60", "61-100", "101-160", ">160"):
        d = buckets[b]
        if d["n"]:
            print(f"  {b:>9}  n={d['n']:>4}   accuracy {d['ok']/d['n']*100:6.2f}%")

    # ---- hard negatives ---------------------------------------------------
    hn = [(r, p) for r, p in zip(scored, pred)
          if r["final_label"] == "legitimate" and SCARY.search(r["text"])]
    if hn:
        wrong = sum(1 for r, p in hn if p == "scam")
        print(f"\n  hard negatives (genuine, contains otp/kyc/block/...): "
              f"{len(hn)}   misread as scam: {wrong} ({wrong/len(hn)*100:.1f}%)")

    # ---- per language -----------------------------------------------------
    print(f"\n{'='*74}\nPER LANGUAGE / SCRIPT")
    print(f"{'='*74}")
    print("  This breakdown matters more than the headline. The test set was")
    print("  sampled from the review queue -- rows our own labeller refused to")
    print("  decide -- stratified by (source, script). So it over-represents")
    print("  exactly the Indic slices that validation already flagged as thin.\n")
    lang_rows = defaultdict(list)
    for r, p in zip(scored, pred):
        lg, script = detect_language(r["text"])
        lang_rows[lg].append((r, p))
    print(f"  {'language':10} {'script':11} {'n':>5} {'accuracy':>10} {'macro-F1':>9}")
    lang_stats = {}
    for lg in sorted(lang_rows, key=lambda k: -len(lang_rows[k])):
        rs = lang_rows[lg]
        yy = [r["final_label"] for r, _p in rs]
        pp = [p for _r, p in rs]
        a = sum(1 for x, z in zip(yy, pp) if x == z) / len(rs) * 100
        pp_per = prf(yy, pp, VALID)
        mf = sum(pp_per[l]["f1"] for l in VALID) / len(VALID) * 100
        script = detect_language(rs[0][0]["text"])[1]
        print(f"  {lg:10} {script:11} {len(rs):>5} {a:>9.2f}% {mf:>8.2f}%")
        lang_stats[lg] = {"script": script, "n": len(rs),
                          "accuracy": round(a / 100, 4)}
    report["by_language"] = lang_stats

    # ---- the known-inconsistent rows --------------------------------------
    present = [r for r in scored if r["sample_id"] in KNOWN_INCONSISTENT]
    report.update({
        "accuracy": round(acc / 100, 4),
        "macro_f1": round(macro / 100, 4),
        "n_scored": len(scored),
        "n_excluded_review": len(excluded),
        "per_class": {l: {k: round(v, 4) if isinstance(v, float) else v
                          for k, v in per[l].items()} for l in VALID},
    })

    if present:
        print(f"\n{'='*74}\nINTERNALLY INCONSISTENT ROWS  (left exactly as annotated)")
        print(f"{'='*74}")
        keep = [r for r, p in zip(scored, pred)
                if r["sample_id"] not in KNOWN_INCONSISTENT]
        kacc, kmacro, kper, _ = score(keep, pipe)
        for r, p in zip(scored, pred):
            if r["sample_id"] in KNOWN_INCONSISTENT:
                ok = "model agrees" if r["final_label"] == p else "model DISAGREES"
                print(f"  {r['sample_id']}  annotator={r['final_label']:16} "
                      f"model={p:16} {ok}")
                print(f"      {r['text'][:88]}")
        print(f"\n  as annotated : accuracy {acc:6.2f}%  macro-F1 {macro:6.2f}%  "
              f"(n={len(scored)})")
        print(f"  flags removed: accuracy {kacc:6.2f}%  macro-F1 {kmacro:6.2f}%  "
              f"(n={len(keep)})")
        print("\n  The second number is NOT the score. It is shown so you can see how")
        print("  much of the headline number depends on two rows you have not yet")
        print("  re-checked.")
        report["excluding_flagged_rows"] = {
            "accuracy": round(kacc / 100, 4), "macro_f1": round(kmacro / 100, 4),
            "n": len(keep)}

    DISAGREE = P / "final_test_disagreements.csv"
    DISAGREE_EXCEL = P / "final_test_disagreements_excel.csv"
    dis = [(r, p) for r, p in zip(scored, pred) if r["final_label"] != p]
    # The Excel-friendly copy is the annotator's working sheet. Prefer its
    # reviewed calls, then fall back to the canonical CSV, and preserve a call
    # only while the sample text and both labels remain unchanged.
    prior_calls = {}
    for prior_path in (DISAGREE_EXCEL, DISAGREE):
        if not prior_path.exists():
            continue
        with prior_path.open(encoding="utf-8-sig", newline="") as fh:
            for old in csv.DictReader(fh):
                call = old.get("your_call", "")
                if call in {"annotator", "model", "unclear"}:
                    key = (old.get("sample_id"), old.get("text"),
                           old.get("annotator_label"), old.get("model_label"))
                    prior_calls.setdefault(key, call)
    preserved_calls = 0
    with DISAGREE.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["sample_id", "text", "annotator_label",
                                           "model_label", "reason", "your_call"])
        w.writeheader()
        for r, p in dis:
            key = (r["sample_id"], r["text"], r["final_label"], p)
            call = prior_calls.get(key, "")
            preserved_calls += bool(call)
            w.writerow({"sample_id": r["sample_id"], "text": r["text"],
                        "annotator_label": r["final_label"],
                        "model_label": p, "reason": r["reason"], "your_call": call})
    print(f"\nwrote {DISAGREE.name}  ({len(dis)} disagreements)")
    print(f"  Preserved {preserved_calls} prior adjudication calls whose text and labels still match.")
    print("  The project owner reports that the disagreement worksheet has been")
    print("  human-reviewed. Any blank or changed row needs review before relying")
    print("  on that worksheet; its decisions are not used to change this score.")

    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
