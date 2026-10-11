# Labelling Rules & Annotation Guide

## The three classes

| Label | Use it when… | Example |
|---|---|---|
| `legitimate` | Expected personal, delivery, account, or transactional message | A genuine bank OTP that says not to share it |
| `marketing_spam` | Unsolicited advertising or bulk promotion, **without** an attempt to steal money or credentials | A quiz-show or real-estate promotion |
| `scam` | Deceives or pressures someone to send money, reveal credentials/OTP, or follow a malicious link | A fake KYC warning demanding OTP entry through a link |
| `review` | Cannot confidently tell | — |

**Precedence rules, applied in this order:**
1. If a message is both promotional **and** fraudulent → `scam`. Fraud beats promotion.
2. If a genuine transaction carries scary words (OTP, KYC, blocked) → `legitimate`.
   This is the hard-negative case and it matters most.
3. If not confidently classifiable → `review`, excluded from training.

## How the automatic labeller decides

`scripts/build_corpus.py` implements these as explicit regex signal banks. Every
decision is recorded in `label_reason` so any row can be audited.

**Strong fraud signals** (`STRONG_FRAUD`) — any hit means `scam`:
- OTP / one-time-password / verification-code solicitation
- KYC + (update|pending|expire|block|verify), account (suspend|block|freeze|deactivate)
- transfer/send/pay + amount + (UPI|account)
- prize/reward/lottery + fee/charge, processing-fee, customs charge
- click/tap/visit + (link|url|http), shortened links
- police/cyber-crime + arrest/case/warrant, "digital arrest"
- legal threats, hour-countdown pressure, "final warning"
- (send|share) aadhaar / PAN / CVV / card number

**Promotional signals** (`PROMOTIONAL`): quiz/horoscope, reply-1, TV channel,
unsubscribe, real estate, EMI, project offers, discount %, "dear customer",
limited period, free delivery.

**Transactional signals** (`TRANSACTIONAL`): "your OTP is…", "do not share",
"credited/debited", "available balance", order id + delivered, out for delivery,
appointment, PNR, salary, autopay, invoice, "your order".

**Personal signals** (`PERSONAL`) — chat shorthand: `??`, `haha`, `lol`, `ok`,
`lve`, `wanna`, `tmr`, `ttyl`, social plans.

**Decision path for old `spam` rows:**
```
strong fraud signal?
  ├─ yes, AND no money/credential demand  -> marketing_spam
  ├─ yes, with money/credential demand    -> scam
  └─ no:
       promotional OR weak-fraud signal   -> marketing_spam
       has URL/phone but no clear signal   -> review
       nothing decisive                    -> review
```

**Decision path for old `ham` rows:**
```
strong fraud signal AND not transactional  -> review  (likely mislabelled)
transactional OR personal marker           -> legitimate
otherwise                                  -> legitimate
```

## Honest limitations of this labeller

1. **It is regex-based, not a human.** The 4,999-row review queue exists precisely
   because these rules cannot decide every row. **It must be resolved by a person**
   before those rows enter training. Do not treat the auto-labels as ground truth
   without sampling them.
2. **Recommended validation:** have a classmate independently label a random sample
   of ~150 rows (stratified by source and class), then compare. Record agreement and
   resolve disagreements in writing. A Cohen's kappa over that sample is a strong
   line for a report.
3. **Non-English text is under-served.** The signal banks are mostly English regexes,
   so Hindi/Telugu scam rows are classified by English-script fragments (URLs,
   digits, `http`) far more often than by meaning. Telugu/Hindi `scam` counts are
   therefore likely **understated** and some should be in the review queue.
4. **`0`/`1` labels** in ysangam are mapped spam→spam, ham→ham before classification.

## Annotation sheet

`data/annotation_sheet.csv` — columns:

```
text | original_label | target_label | source | language | script |
real_or_synthetic | template_or_source_id | notes
```

For hand-labelling, fill `target_label` with one of
`legitimate` / `marketing_spam` / `scam`, and put the reason in `notes`.
If you cannot decide, use `review`.

## Class balance observed

The corpus is heavily imbalanced toward `legitimate`, which is realistic — real
inbox traffic is mostly legitimate. Consequences:
- Always read **macro-F1**, never accuracy alone.
- If a real deployment matters more than recall, tune the decision threshold for
  higher precision; if missed scams are costly, tune for recall on `scam`.
- Report metrics at the natural skew. A balanced-accuracy number from a balanced
  test set would flatter the model.