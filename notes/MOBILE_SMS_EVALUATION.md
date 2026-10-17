# Mobile SMS integration and bias check

Run: 2026-10-17. This is a local evaluation note; the redacted message data and
generated CSVs remain ignored by git.

## Mobile sample

- 320 inbound SMS were exported; repeated templates were collapsed.
- 188 distinct templates were reviewed; 186 had usable labels and 2 stayed
  unresolved and were excluded.
- Labels: 126 legitimate, 59 marketing spam, 1 scam.
- Detected language: 145 English, 36 Tenglish, 2 Hinglish, 2 Hindi, 1 Telugu.
- This is one person's phone history, so it is strongly skewed by sender mix,
  language and message types. One scam example cannot train or measure scam
  detection reliably.

## Current grouped validation

Model: char_wb(2,5) TF-IDF + balanced LogisticRegression. The split is grouped;
no `dup_group` crossed train/validation/test. The pre-existing blinded human
holdout was checked and had zero overlap with the trainable corpus. The old
contaminated `split_test.csv` was not scored.

| Metric | Result |
|---|---:|
| Validation rows | 4,174 |
| Accuracy | 94.44% |
| Macro-F1 | 85.62% |
| Legitimate precision / recall / F1 | 95.16% / 99.24% / 97.16% |
| Marketing spam precision / recall / F1 | 94.19% / 80.91% / 87.04% |
| Scam precision / recall / F1 | 75.22% / 70.25% / 72.65% |
| Scam examples missed | 36 / 121 |

The separate published human-labelled result remains 74.4% macro-F1 on 305
messages, labelled by one annotator. It is not the same sample as this grouped
validation and is still the more realistic manual review result.

## Language slices (validation)

| Language | n | Accuracy | Macro-F1 | Caveat |
|---|---:|---:|---:|---|
| English | 3,043 | 97.70% | 90.04% | Largest slice; scam recall 64.1% |
| Hinglish | 623 | 95.02% | 78.53% | Scam support 23 |
| Tenglish | 341 | 100.00% | 66.67% | No scam examples; accuracy is misleading |
| Telugu | 87 | 19.54% | 41.30% | Marketing-spam recall 0/70 |
| Hindi | 80 | 23.75% | 12.79% | Marketing-spam recall 0/61 |

**Bias finding: yes.** The validation data show a severe language disparity:
Hindi and Telugu accuracy is near chance, while the English slice is strong.
The Hindi/Telugu slices are small and mostly synthetic, so the exact rates are
uncertain, but they are clearly not evidence of multilingual readiness. The
model should not be presented as reliable for those languages.

The 28 mobile templates that landed in validation scored 75.0% accuracy
(21/28); this includes 23 legitimate, 4 marketing-spam and only 1 scam message,
which the model missed. This is a useful warning, not a statistically stable
phone-SMS benchmark.

## Grouping and next step

The mobile templates were grouped against one another, and exact-text overlap
with the prior corpus was zero. A complete near-duplicate comparison between
the new mobile source and every older source was not completed because the full
corpus near-duplicate rebuild is slow. Treat the validation results above as
indicative until that cross-source near-duplicate audit is completed.

Collect more independently reviewed Hindi/Telugu messages and scam examples,
then have a second annotator review a held-out sample. Do not use this one-phone
sample alone to claim that the multilingual bias is fixed.
