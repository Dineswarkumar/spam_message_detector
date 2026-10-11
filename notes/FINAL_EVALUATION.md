# Final evaluation — 74.4% macro-F1, and why that number needs its caveats

Produced by `scripts/score_final_test.py`, which is the only script in this
project permitted to print an accuracy figure.

## The headline

| metric | value |
|---|---|
| accuracy | **74.43%** |
| macro-F1 | **74.44%** |
| rows scored | 305 of 310 |
| rows excluded as "undecidable" | 5 |
| annotators | **1 — no Cohen's kappa exists** |

Per class:

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| legitimate | 59.5% | 85.7% | 70.2% | 84 |
| marketing_spam | 74.7% | 78.5% | 76.5% | 79 |
| scam | 92.1% | 65.5% | 76.5% | 142 |

Confusion (rows = annotator):

|  | → legitimate | → marketing_spam | → scam |
|---|---|---|---|
| **legitimate** | 72 | 4 | 8 |
| **marketing_spam** | 17 | 62 | 0 |
| **scam** | 32 | 17 | 93 |

## Read the caveats before quoting this

**1. This is not a representative sample.** The 310 messages were drawn from
`review_queue.csv` — the messages the corpus labeller itself refused to decide —
stratified by (source, script). By construction this is the hardest slice
available. It is not "a random set of SMS".

**2. It is not comparable to the 91.94% validation macro-F1.** That figure is on
ordinary grouped held-out data. Both numbers are true; they answer different
questions. Quoting 74.4% without saying so would understate the model; quoting
91.9% as if it were test performance would be a lie.

**3. Single annotator.** No second labeler, so no kappa. This measures agreement
with one person's judgement, not with an agreed gold standard. The annotator's
review of the initial disagreements is complete, but residual label error and
inter-annotator agreement remain **unmeasured**.

**4. Length is not doing the work.** Length-controlled accuracy:

| length | n | accuracy |
|---|---|---|
| ≤60 | 15 | 73.3% |
| 61–100 | 127 | 63.8% |
| 101–160 | 148 | 83.8% |
| >160 | 15 | 73.3% |

**5. By language:**

| language | script | n | accuracy |
|---|---|---|---|
| english | latin | 196 | 75.0% |
| hinglish | latin | 75 | 72.0% |
| tenglish | mixed | 21 | 100.0% |
| hindi | devanagari | 13 | 38.5% |

Hindi (n=13) and Tenglish (n=21) are far too small to support a claim. The
Hindi figure sits near chance for a 3-class problem, consistent with the
`ADEQUACY CHECK` in the corpus build log.

## What was fixed before scoring

- 4 rows labelled `spam` were confirmed by the annotator to mean **scam** and
  normalised. `review` was kept as the project's own undecidable class and
  excluded from scoring — counted neither right nor wrong.
- Two rows (`FT0003`, `FT0031`) were found carrying labels that contradict their
  identical sibling messages. **They were not silently corrected.** The score is
  reported both ways: 74.43% as annotated, 74.92% with the two flagged rows
  removed. The gap is small, but the point stands that a gold set should not be
  quietly edited to flatter the model.

## Disagreement review

78 of 305 rows initially disagreed with the model. The annotator reviewed those
cases and completed the `your_call` column in
`final_test_disagreements_excel.csv`. The original disagreements included both
types of issue. From the largest group (annotator=scam, model=legitimate, 32 rows):

- **Model is wrong:** `Aapke naam pe FIR darj ho gayi hai. Bachne ke liye
  turant call karein.` — classic police blackmail, read as legitimate.
  `Aapka EPF balance Rs 2 lakh withdraw karne ke liye Aadhaar OTP chahiye.` —
  explicit OTP solicitation, read as legitimate.
- **Label is arguably wrong:** `आपके खाते से अनधिकृत लेनदेन हुआ है। तुरंत
  अपना पासवर्ड बदलें।` — this is a plausible genuine bank fraud alert.

The completed decisions are the annotator's human review of these cases. They
make the disagreement record auditable, but they are not a second independent
annotation and do not provide inter-annotator agreement. The headline 74.43%
accuracy / 74.44% macro-F1 above remains the score against the original labels;
it has not been recomputed using the post-review decisions, so the model-informed
adjudication is not presented as an independent test score.
