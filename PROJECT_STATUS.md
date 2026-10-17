# Spam Shield — Project Completeness Report

Generated 2026-10-17. This report includes the latest local mobile-SMS
integration and validation metrics; see `notes/MOBILE_SMS_EVALUATION.md` for
the focused bias check and its limitations.

**One-line summary:** the ML pipeline and detection engine are finished and
verified; the trained artifact is connected to the API and the API serves the UI
at `/app`; response mapping and input limits have been smoke-checked in-process,
but a browser-to-server roundtrip and responsive interaction review remain. The
single annotator has human-reviewed the 78 disagreements; there is still no
second annotator or agreement statistic.

---

## 1. Scorecard

| Area | Completeness | Verified how |
|---|---|---|
| Dataset audit | **100%** | `scripts/audit_dataset.py` on all 8 sources |
| Synthetic data generation | **100%** | 56 templates × 4–5 languages, leakage-proven |
| Corpus build + labelling | **100%** | 29,040 trainable rows after adding 186 reviewed mobile-SMS templates; 6 guards, fixture-tested |
| Context guards | **100%** | 235/235 template fixtures + 9/9 anti-suppression |
| Split construction | **100%** | grouped by template/dup-group, 0 overlap asserted |
| Model + selection | **100%** | 4 candidates × 3 seeds, documented in `notes/MODEL_SELECTION.md` |
| Detection engine (rules) | **100%** | 19/19 rule fixtures |
| Backend API | **90%** | model artifact loaded; prediction, validation and UI-serving paths smoke-checked in-process; HTTP roundtrip still to confirm |
| Frontend | **85%** | API response mapping and JS syntax checked; browser interaction and responsive review outstanding |
| Evaluation | **80%** | 305 rows scored; annotator human-reviewed all 78 disagreements; no second annotator/kappa |
| Documentation | **90%** | 6 notes + AGENTS.md; UI copy rewritten |
| Deployment | **45%** | `render.yaml` added; never deployed |

---

## 2. ML Pipeline

### 2.1 Data sources — all audited, all deduped

| Source | Claimed | Real unique | In corpus | Dupes |
|---|---|---|---|---|
| UCI SMS Spam Collection | 5,572 | 5,572 | 5,288 | ~0% |
| `Dataset_5971` phishing | — | +945 new | 5,573 | 84% overlap with UCI |
| `indian_spam.csv` (Yadav 2011) | 2,000 | 1,970 | 1,558 | 1.5% |
| Atharva taxonomy | 605 | 563 | 437 | 7% |
| `ysangam` Indian Cyber Scam | 10,000 | **743** | 289 | 92.6% |
| `karanverma19` | 120 | **49** | 0 | 59.2% — rejected |
| legacy `multilingual_fraud` | — | 232 of 600 | 561 rows | 61.3% |
| `uniquedata` card claims | 10k–100k | **25** | 0 | — |

`ysangam` is a police-impersonation detector wearing a spam label (85.2% scam
after dedup). `karanverma19` was rejected — its marker word is glued onto
legit rows too.

### 2.2 Corpus

```
29,040 trainable rows
  legitimate      17,338
  scam             6,981
  marketing_spam   4,721

 1,836 rows parked in review_queue.csv (6.4%) — excluded, not guessed
```

By source: synthetic 11,948 · phishing5971 5,573 · uci 5,288 ·
synthetic_marketing 3,200 · indian2011 1,558 · legacy_ml 561 · atharva 437 ·
ysangam 289 · mobile_sms_review 186

### 2.3 Synthetic templates (the multilingual layer)

| Family | Templates | Languages |
|---|---|---|
| Scam | 12 | en / Hinglish / Hindi / Tenglish |
| Legitimate (hard negatives) | 33 | en / Hinglish / Hindi / Tenglish |
| Marketing spam | 11 | 5 variants |

**235 fixtures** = every template × every language. The 33 legitimate templates
were the deliberate fix for the project's worst gap: real bank OTPs, KYC
renewals, bill reminders, EMIs, refunds, government credits — the messages that
contain *account*, *blocked*, *verify* but are **not** fraud.

### 2.4 Splits

| Slice | Rows | Grouping | Status |
|---|---|---|---|
| train | 18,945 | `template_id` / `dup_group` | used for fitting |
| val | 4,174 | same | only iteration surface |
| test | 5,921 | same | **contaminated — never scored** |

`split_test.csv` is kept for provenance only. All four candidates were scored on
it during the original comparison, so it cannot be un-contaminated.

**Holdout reservation is enforced, not assumed.** `scripts/reserve_holdout.py`
strips any row appearing in the 310-row blinded sheet from the corpus, and
`make_final_splits.py` aborts if one leaks. This fired for real: widening the OTP
patterns moved 3 `atharva` rows from review into training while they were already
in the blinded sheet.

### 2.5 Model

```
char_wb(2,5) TF-IDF  ->  LogisticRegression(C=4, balanced)
artifact: 2.5 MB
```

No word features, by measurement rather than taste — see §9.

---

## 3. Detection Engine

Three layers, and **the rule layer never overrides the model**. It is additive
and every hit is shown in the UI so a user can dispute it.

```
input
  |
  +-- model  -> verdict + confidence  (source: "model")
  |
  +-- rules  -> signal list          (source: "rule")
  |
  +-- system -> language / script / distractor keywords (source: "system")
```

### 3.1 The 6 rules

| Rule | Severity | Catches |
|---|---|---|
| `credential_request` | high | "share/send your OTP / PIN / password" |
| `identity_document_request` | high | Aadhaar / PAN / CVV solicitation |
| `authority_impersonation` | high | police / cyber cell / CBI / NCB |
| `payment_demand` | high | "pay Rs N to this UPI id" |
| `malicious_link` | medium | shorteners and lookalike domains |
| `prize_with_fee` | medium | lottery / prize + processing fee |

### 3.2 The guards — one definition, shared

`backend/guards.py` is imported by **both** `scripts/build_corpus.py`
(training-time labelling) and `backend/predictor.py` (runtime). Never duplicate
these inline; a guard that drifts between labelling and inference means the model
is trained under one rule and judged under another.

| Guard | Meaning |
|---|---|
| `PROHIBITION` | "do not share" negates the verb → a warning, not a demand |
| `BILLING_CONTEXT` | a payment demand inside bill/due/statement/EMI is a bill |
| `OFFICIAL_ROUTE` | points at an official net-banking portal |
| `COMPLETION` | reports finished work ("has been updated", "no action needed") |
| `completed_but_unclaimed()` | completion **and** no live ask → legitimate |

Every fraud pattern must require a **DEMAND or COERCION**, never a bare topic
noun. Bare `शुल्क` / `केवाईसी` / `ओटीपी` once flipped 98 genuine OTP rows into
review. Protected by **9 anti-suppression fixtures**: scams that deliberately
borrow legitimate phrasing must still classify as scam.

### 3.3 Distractor panel

Shows the scary vocabulary a message contains *without* acting on it — `account`,
`blocked`, `verify`, `security`, `password`, `otp`, `kyc`, `pending`, `freeze`.
This is what teaches a user why a real bank alert was allowed through.

---

## 4. Backend

`backend/` · FastAPI · loads `backend/artifacts/model.joblib`; `/app` serves the
frontend from the same origin. Model prediction and input validation were
smoke-checked in-process; the current environment blocked a local socket test.

| Endpoint | Purpose |
|---|---|
| `GET /health` | model_loaded, model_version, classes, training_rows, evaluation_status |
| `POST /predict` | verdict, confidence, language, script, signals[], latency_ms |
| `GET /` or `/app` | frontend, served on the same origin as the API |
| `GET /api` | service information |

| File | Role |
|---|---|
| `train.py` | builds + fits + exports the artifact, writes `metadata.json` |
| `predictor.py` | inference, language/script detection, rule layer |
| `guards.py` | the shared context guards |
| `main.py` | FastAPI app, API routes and same-origin frontend route |
| `start_spam_shield.ps1` | starts the backend and opens the frontend automatically |
| `test_rules.py` | 19 rule fixtures |
| `requirements.txt` | pinned for Render |
| `render.yaml` | Render web-service build, start and health-check configuration |
| `artifacts/` | `model.joblib` (2.5 MB) + `metadata.json` |

`metadata.json` deliberately carries **no accuracy number** — it carries
`evaluation_status: indicative_single_annotator_reviewed`, the known limitations,
and the full model-selection rationale.

---

## 5. Frontend

`design/index.html` — 125,892 bytes, single file, no build step, no framework.
Two script blocks both pass `node --check`.

| Section / feature | Status |
|---|---|
| Message input + analyse | done |
| Verdict card (confidence, class, latency) | done |
| Signals list with source tags (model / rule / system) | done |
| Distractor-keyword panel | done |
| Sample message chips | done |
| Heuristic-fallback marker + cold-start retry | done |
| **Safety Rules** section | done |
| **Report Fraud** section — 8 verified official channels | done |
| Helpline CTAs: **1930** (cyber fraud, 24×7), **112** (police), **1915** (consumer) | done |
| **Engine** section with eval banner | done |
| Sticky tab bar | done |
| GitHub author chip (avatar + name, links to profile) | done |
| Footer + privacy note + disclaimer | done |
| Dark / light theme | done |
| Responsive layout | done |
| `api/CONTRACT.md` link | done, file exists |

### ⚠️ The gap

Screenshots of the light and dark themes and the main sections have been reviewed.
The interface appears coherent in those captures; the screenshots do not verify
button interactions, the theme toggle, or responsive behavior at known viewport
sizes. Code review found hover and keyboard-focus states, reduced-motion support,
and persistent theme selection. The Engine tab was added to active-section
tracking. Direct click-through remains unverified.

---

## 6. Evaluation — what we can honestly claim

| | Validation | Human-labelled test set |
|---|---|---|
| Rows | 4,174 | 305 |
| Accuracy | 94.44% | **74.43%** |
| Macro-F1 | 85.62% | **74.44%** |
| Hard-negative miss | 0% (n=377) | 17.9% (n=28) |
| Annotators | n/a | **1 — no kappa** |

Current validation is a new grouped split after adding mobile examples; it
supersedes the prior 4,082-row validation figure. It remains an iteration
metric, not the final score. The mobile sample's 28 validation rows scored 75%
accuracy (21/28), with only one scam example. See
`notes/MOBILE_SMS_EVALUATION.md` for the language breakdown and the remaining
cross-source near-duplicate audit limitation.

**These are not comparable.** The test set was drawn from the review queue — the
messages our own labeller refused to decide — so it is the hardest slice
available, not a random sample of SMS.

By language on the test set: English 75.0% (n=196) · Hinglish 72.0% (n=75) ·
Tenglish 100% (n=21) · Hindi 38.5% (n=13). The last two are too small to claim.

### Test coverage

| Suite | Result |
|---|---|
| `scripts/test_template_labels.py` | **235/235** |
| guard anti-suppression | **9/9** |
| `backend/test_rules.py` | **19/19** |
| `scripts/reserve_holdout.py --check` | **0 leaks** |

---

## 7. Honest limitations

1. **Hindi (38.5%, n=13) and pure-Telugu are near chance.** Not enough rows for a
   per-language claim. The corpus `ADEQUACY CHECK` block flags this every build.
2. **Tenglish is synthetic-only** — 1 real row. Needs a fluent native speaker.
3. **No inter-annotator agreement.** The 74.4% score measures agreement with one
   annotator. That annotator has reviewed all 78 disagreements and recorded a
   decision for each. This resolves the review task, but it does not create a
   second independent label or Cohen's kappa. The published score remains the
   score against the original labels; it has not been recomputed from the
   post-review decisions.
4. **Two gold-set rows are internally inconsistent** (`FT0031`, `FT0003`) and
   were deliberately left uncorrected. Score as annotated 74.43%; with those two
   removed 74.92%.
5. **The marketing/scam boundary is a judgement call**, not a crisp fact.
6. **~6.4% of the corpus sits in the review queue**, excluded from training.
7. **Frontend unverified in a browser.**

---

## 8. Feature ideas, prioritised

### Tier 1 — cheap, high value, unblocks honesty

| # | Idea | Why it matters |
|---|---|---|
| 1 | **Verify frontend interactions and responsive widths** | Screenshots were reviewed, but click-through and known viewport sizes remain unchecked. |
| 2 | **Tenglish native-speaker review** (150 rows) | Gates any Tenglish claim. |
| 3 | **Span highlighting** — underline the exact words that fired each rule | Turns "the model says scam" into "these 6 words did it". Biggest trust win per line of code. |

### Tier 2 — real product value

| # | Idea | Notes |
|---|---|---|
| 5 | **Sender allowlist** (RBI-listed banks, known OTTs) | A verified sender override would kill most remaining false positives. Needs an RBI/DLT list. |
| 6 | **Batch paste** — analyse many messages at once | Real users forward whole threads, not one SMS. |
| 7 | **PWA + offline** | Installable, works without signal. No backend change. |
| 8 | **Feedback loop** — "this was wrong", stored locally, exported as CSV | Feeds future active learning and gives the reviewer a work queue. |
| 9 | **Entity extraction** — which UPI ID, which number, which link | Actionable, not just a label. |
| 10 | **Redaction mode** — mask amounts/account numbers before sharing a result | Fits the existing privacy promise. |

### Tier 3 — larger bets

| # | Idea | Honest cost |
|---|---|---|
| 11 | **Fine-tune IndicBERT / MuRIL** | Would likely help the Hindi slice. Heavy, and the current weakness is data volume, not architecture. |
| 12 | **Android SMS permission + on-device scan** | Turns it into an actual product. Big scope. |
| 13 | **Screenshot OCR scan** | Reuses everything above. Moderate effort. |
| 14 | **Multilingual UI** | Currently English-only UI over multilingual detection. |
| 15 | **Temporal features** (burst frequency, sender novelty) | Needs a gateway or an on-device history. Cannot be a pure text classifier. |

---

## 9. The one lesson worth keeping

The previous shipping model was **LinearSVC on word+char TF-IDF**, chosen for a
24-point hard-negative advantage over word+char LR (2.0% vs 26.0% miss rate).

That advantage was **not a property of the classifier.** It was missing training
data. With one legitimate KYC template against four scam ones, *any* model had to
distrust word features to avoid false scam calls.

After closing the data gap:

| model | macro-F1 (3 seeds) | hard-neg miss |
|---|---|---|
| word+char LR | 92.51% ± 2.00 | 1.52% |
| **char-only LR** | **93.16% ± 1.07** | **1.19%** |
| word+char SVC | 91.61% ± 3.69 | 1.52% |

The advantage vanished. The decision was reversed.

**Before defending or reversing a model choice, ask what it was actually
compensating for.**

---

## 10. Commands

```powershell
# verification (all must pass before shipping anything)
python scripts/test_template_labels.py     # 235/235 + 9/9
python backend/test_rules.py               # 19/19
python scripts/reserve_holdout.py --check  # 0 leaks

# rebuild (in order)
python scripts/generate_synthetic.py
python scripts/build_corpus.py
python scripts/reserve_holdout.py
python scripts/make_final_splits.py
python scripts/model_comparison.py --val-only
python scripts/seed_stability.py
python backend/train.py

# scoring (the ONLY script allowed to print accuracy)
python scripts/score_final_test.py

# serve
cd backend; python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## 11. Key files

```
AGENTS.md                        project rules — read first
PROJECT_STATUS.md                this file
notes/MODEL_SELECTION.md         full model-choice evidence
notes/FINAL_EVALUATION.md        score + all caveats
notes/DATASET_AUDIT.md           per-dataset health
notes/SYNTHETIC_METHODOLOGY.md   how templates were grounded
notes/LABELLING_RULES.md         the 3-class decision rule
design/index.html                the frontend
api/CONTRACT.md                  response contract
data/processed/final_test_disagreements_excel.csv   78 human-reviewed disagreements
```
