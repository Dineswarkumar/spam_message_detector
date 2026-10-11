# Model selection — how the shipping choice was reversed by measurement

Short version: the previous project decision was **LinearSVC on word+char
TF-IDF**, chosen for a 24-point hard-negative advantage. That advantage turned
out to be missing training data wearing a model's clothes. Closing the data gap
deleted the advantage. The shipped model is now **char_wb(2,5) TF-IDF →
LogisticRegression**, chosen on a different axis.

## Why hard negatives are the primary axis

In this problem a false "scam" on a genuine bank SMS is much worse than a
false "legitimate" on a scam. A bank OTP that gets flagged is money the user
cannot receive; a scam that slips through is one bad day. So every candidate is
scored first on **hard-negative miss rate**: legitimate messages containing
`otp | kyc | verify | block | suspend | account | freeze | restrict | pending |
expire` or their Indic equivalents, read as `scam`.

## Round 1 — before the legitimate-data gap was closed

Grouped, stratified, zero leakage, validation only:

| model | val macro-F1 | hard-neg miss |
|---|---|---|
| word-only → LogReg | 88.13% | 28.5% |
| word+char → LogReg | 89.29% | 26.0% |
| char-only → LogReg | 90.67% | 19.3% |
| **word+char → LinearSVC** | 89.99% | **2.0%** |

LinearSVC shipped. The stated reason: word n-grams latch onto "blocked",
"verify", "account" and flag genuine bank alerts — the exact failure this
project exists to prevent. Char n-grams carry the code-mixed text, where
whitespace tokenisation fails.

That reasoning was plausible and it was **wrong about the cause**. The gap was
not a property of word features. The legitimate side of the KYC and billing
template families was one template deep (`lg16`, `lg12`) against four scam
templates each. With no examples of "KYC renewal that is genuine", the only way
for *any* model to avoid false scam calls was to distrust word features
entirely. The classifier was compensating for absent data.

## What changed

1. **18 legitimate transactional templates added** (`lg17`–`lg34` in
   `scripts/generate_synthetic.py`), covering the legitimate twin of each scam
   family: KYC renewal, bill reminders, loan EMI, refunds, cashback,
   government credits, document updates, travel, healthcare, education, ATM,
   deposit maturity. All in 4 languages. These use the *same* scary vocabulary
   as their scam counterparts by construction.

2. **Context guards extracted into `backend/guards.py`** and imported by both
   the corpus labeller and the runtime rule layer. Previously they existed only
   in `predictor.py`, so the labelling-time and inference-time judges disagreed.

   - `PROHIBITION` — "do not share" negates the verb, so a share request is a
     warning to the reader, not a demand.
   - `BILLING_CONTEXT` — a payment demand inside "bill / due / statement / EMI"
     is a bill, not an activation demand.
   - `OFFICIAL_ROUTE` — pointing at an official net-banking portal.
   - `completed_but_unclaimed()` — a message reporting finished work *and*
     asking for nothing. Every scam demands a future action; none report a
     completed one. A completion marker **plus** a live ask is still a scam and
     is not suppressed.

3. **Code-mixed acronym fix.** The Indic fraud patterns only matched Indic
   transliterations (`ओटीपी`, `ఓటీపీ`). A Hindi or Telugu message writing the
   acronym in Roman script — exactly what code-mixing produces — evaded them
   entirely. Now `(ओटीपी|\botp\b)` etc.

## Round 2 — after, across three grouped splits

`scripts/seed_stability.py`, seeds 42 / 7 / 2026, validation only:

| model | macro-F1 (mean ± half-range) | hard-neg miss |
|---|---|---|
| word-only → LogReg | 80.77% | — |
| word+char → LogReg | 92.51% ± 2.00 | 1.52% |
| **char-only → LogReg** | **93.16% ± 1.07** | **1.19%** |
| word+char → LinearSVC | 91.61% ± 3.69 | 1.52% |

**The hard-negative advantage is gone.** 26.0% → 1.52% for word+char LR, and
2.0% → 1.52% for SVC. All three candidates are now effectively tied on the axis
that originally decided it.

macro-F1 differences sit *inside* the winner's own seed spread (char-only leads
by 0.65 points, spread is ±1.07). `seed_stability.py` prints the verdict itself:
**not stable — treat as a tie and decide on a different axis.**

## The decision

| axis | char-only | word+char LR | word+char SVC |
|---|---|---|---|
| hard-neg miss | **1.19%** | 1.52% | 1.52% |
| seed stability | **±1.07** | ±2.00 | ±3.69 |
| macro-F1 | 93.16% | 92.51% | 91.61% |
| has the word-n-gram false-scam failure mode | no | yes | yes |
| confidence honesty | native `predict_proba` | native | needed sigmoid calibration |

char-only + LogisticRegression wins on every axis that separates them. It also
dropped the artifact from 10.1 MB to 2.5 MB.

## Known miss, stated rather than hidden

    "OTP hai 482910. Humare agent ko share karein for verification."

The shipped model returns **marketing_spam** at P(scam)=0.35. Both word+char
models return scam.

This was checked rather than waved away:

- On the full short code-mixed scam slice (45 validation rows ≤110 chars), all
  three models tie at **97.8% scam recall**. The aggregate is unaffected.
- The difference is this single message. Overfitting a shipping decision to one
  hand-picked example is the same error as trusting a row count, so it did not
  flip the choice.
- The **rule layer fires `credential_request`** on this message, and rule hits
  are additive and visible in the UI. The user sees the warning even though the
  model headline is wrong. That is exactly what the disclosed rule layer is for.

## What this teaches, for whoever tunes this next

The previous decision was not stupid, and that is what made it dangerous — it
was a defensible causal story built on a confound. Before defending or reversing
a model choice, ask **what was it actually compensating for**. If the answer is
"missing data", the model choice is the wrong lever.