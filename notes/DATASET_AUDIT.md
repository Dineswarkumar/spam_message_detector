# Dataset Audit — Findings

Date: 2026-10-07
Working dir: `T:\B-Tech\Projects\spam-msg-detector`

All numbers below were **measured** with `scripts/audit_dataset.py` and
`scripts/probe_duplicates.py`, not taken from dataset READMEs. Language detection
is by Unicode script range plus a Hinglish marker-word heuristic, so it does not
trust self-reported `language` columns.

---

## Headline: every candidate is worse than its row count claims

| Dataset | Claimed | **Real unique** | Duplicates | Verdict |
|---|---|---|---|---|
| `ysangam/Indian_Cyber_Scam` | 10,000 | **743** | 92.6% | unusable as-is, taxonomy gold |
| `karanverma19/Indian_Multilingual_Scam` | 120 | **49** | 59.2% | reject |
| legacy `multilingual_fraud_dataset.csv` | — | **232** (of 600) | 61.3% | near-worthless |
| Atharva taxonomy (`dataset.py`) | 605 | **563** | 7% | **best raw text we have** |
| UCI SMS Spam Collection | 5,572 | 5,572 | ~0% | solid English baseline |

Row count is not data volume. Every multilingual dataset inflated itself.

---

## 1. UCI SMS Spam Collection — `data/raw/baseline_english/`

5,572 English SMS, 4,825 ham / 747 spam (86.6 / 13.4), CC BY 4.0, no nulls.
This is our English backbone and the *only* fully trustworthy file we have.

Caution: spam averages ~138 chars vs ~71 for ham. A model can score well by
learning **length alone**. Our eval must report length-controlled results.

## 2. Legacy old repo — `data/raw/legacy_old_repo/`

- `multilingual_fraud_dataset.csv` — 600 rows, 300/300, but only **232 unique**.
  75.5% latin / 15.8% Devanagari / 14.5% Telugu. **Zero Hinglish** by our
  heuristic. `p50` length 40 chars, `max` 65 — everything is clipped short.
- `dataset.csv` — the 6,172-row merge actually used for training.
  83% ham / 17% spam. **97.6% latin. Devanagari 1.5%, Telugu 1.4%.**

That last number is the whole story of the old project. 6,172 rows of which
~180 were Indian-language. The "multilingual" claim was carried by 3% of the data
and one char-TFIDF vocabulary. **The old model never had a multilingual dataset.**

## 3. `ysangam` 10k — the important one

Rows: 10,000 → **743 unique**. Column `language_style` is constant within 100%
of duplicate groups, and `contains_blackmail` in 100%: pure re-sampling of
metadata, no new information.

After dedup the class balance inverts hard:

- `1` (scam): **633 (85.2%)**
- `0` (legit): **110 (14.8%)**

Category breakdown explains why: `police_digital_arrest` alone is 402 of the 633
scams. The dataset is essentially "digital-arrest scam" with 110 unrelated
benign greetings. Train on it and you build a police-impersonation detector
labelled "spam detector".

**But the taxonomy is excellent and worth keeping.** Scam categories found:
`police_digital_arrest`, `police_blackmail`, `bank_kyc`, `lottery`, `amazon`,
`relative`, `aadhaar`. Metadata columns (`urgency_level`, `caller_type`) are a
ready-made feature schema. Keep as `data/raw/needs_verification/`.

Note: it is call-transcript style (`Ji namaskar`, `Hinglish`, 100% Latin script,
zero Devanagari) — **not** the SMS-with-OTP-link format of real SMS fraud.

## 4. `karanverma19` 120 — rejected

49 unique. Most common ending `" immediately"` in 30/120 rows. The word `त`
appears in 72 rows (60%) purely from the glued `" jaldi kare"` suffix — note it
is appended to **legit** rows too ("Your payment of ₹899 has been received jaldi
kare"), so it carries no signal, just noise. Confirmed template filler. Do not
use for training.

## 5. Atharva taxonomy — best multilingual text in hand

563 distinct multi-word strings in `PHISHING_MESSAGES` + `LEGIT_MESSAGES`.
Genuinely covers English, Hinglish (`Aapka ATM card suspend ho gaya hai...`)
and Devanagari, with realistic Indian entities: UPI, Aadhaar, PAN, EPF, CIBIL,
NREGA, Flipkart, Swiggy, PhonePe, Ola. Small but **real** — no repeated
boilerplate detected.

Use for: (a) taxonomy design, (b) a supervised category classifier,
(c) few-shot examples, (d) augmenting our thin multilingual slice.

---

## 6. `Dataset_5971` (SMS Phishing Dataset) — good data, low marginal value

Added by user, in `dataset/SMS PHISHING DATASET FOR MACHINE LEARNING AND
PATTERN RECOGNITION/`. Also the SMS slice of the `ealvaradob/phishing-dataset`
HF card (most-starred phishing dataset on HF, 64 likes).

- 5,971 rows, **5,831 unique — only 2.3% duplicates.** Genuinely clean.
- Labels: `ham` 4,844 / `Smishing` 616 / `spam` 466 / `Spam` 23 / `smishing` 22.
  **Five distinct casings of three concepts** — must normalize before merging.
- Useful feature: distinguishes **smishing** (fraud) from **spam** (marketing).
  That distinction is exactly our target and is not present in UCI.
- Has `URL`, `EMAIL`, `PHONE` columns — extractable features, currently unused.
- 100% Latin script, ~0% Hinglish. Adds no language coverage.

**Critical: it mostly duplicates UCI.** Measured with `scripts/check_overlap.py`:

```
A (UCI)      unique: 5,159
B (5971)     unique: 5,831
OVERLAP:        4,886   <- 83.8% of B is already in A
UNION:          6,104   <- what you actually train on
label agreement on overlap: 4,886 agree / 0 disagree
```

So of 5,971 rows it only adds **945 genuinely new messages**. It confirms the
`redasers/difraud` dataset card, which states its SMS slice was built from UCI
plus this file and deduplicated. Useful for the smishing/spam split, marginal as
a volume source.

## 7. `uniquedata/spam-text-messages-dataset` — unusable, rejected

HF card claims "10K<n<100K". **The CSV contains 25 data rows.** The card also
describes a per-row screenshot, and 25 `images/*.jpg|png` files are present, so
the 25 matches the images.

Also: delimiter is `;` with an unnamed second column and 7 trailing empty
fields, so naive CSV parsers produce 0-length text and 100% garbage. Content is
African/Asian carrier marketing (MTN, Telkom, Airtel, Carrefour, PharmEasy) —
all spam, zero ham, zero Indian, zero labels.

Verdict: not a spam *classifier* dataset. At 25 rows it contributes nothing.

---

## Revised corpus estimate

| Source | Unique | New vs what we had | Language coverage |
|---|---|---|---|
| UCI SMS Spam | 5,159 | — | English |
| Dataset_5971 (deduped vs UCI) | 945 | +945 | English, smishing |
| Atharva taxonomy | 563 | +563 | En / Hinglish / Devanagari |
| ysangam deduped | 743 | +743 | Hinglish (call style) |
| legacy multilingual salvage | 232 | +232 | En / Devanagari / Telugu |
| **total** | **~7,642** | | |

Real unique English+smishing is now ~6,100 and solid. **Multilingual is still
~1,538 and still the weak axis.** Volume is no longer the blocker; per-language
coverage is.

## The real gap, stated plainly

| Need | Have | Gap |
|---|---|---|
| English spam/ham | 5,572 real | none |
| Hindi (Devanagari) | ~180 unique | **~3,000 needed** |
| Hinglish | ~130 unique | **~3,000 needed** |
| Legitimate Indian transactional SMS (hard negatives) | ~110 trivial greetings | **the worst gap** |

The last row is the one that matters most and nobody has it. Real bank OTPs,
delivery updates, appointment reminders, salary credits. Those are the messages
a naive model mislabels, because they contain words like "account", "blocked",
"verify" without being scams. **Without them we will ship a model that flags
every bank SMS.**

---

## Decision

1. Keep UCI as the English anchor.
2. Harvest the Atharva strings + the `ysangam` 743 unique into one curated pool,
   split by category. Use for taxonomy and for augmenting language coverage.
3. **Do not** train on any of these inflated row counts. Effective unique volume
   is ~800 multilingual rows against 5,572 English.
4. Source genuine Indian transactional/OTP SMS for hard negatives. This is the
   blocking gap and it will need manual collection or a legitimate source.
5. Any synthetic generation we do ourselves **must** be grouped-split by
   template ID, or the test score is meaningless. Borrow the method from
   `Sivadharni/Code-Mixed-Spam-Scam-Detector`.

## Files here

```
data/raw/baseline_english/UCI_SMS_Spam_Collection.zip + SMSSpamCollection
data/raw/legacy_old_repo/{spam,dataset,multilingual_fraud_dataset}.csv
data/raw/needs_verification/ysangam_india_cyber_scam.csv      (10k rows / 743 unique)
data/raw/needs_verification/karanverma19_ultra_premium_scam.csv (rejected)
data/raw/phishing_taxonomy/atharva_dataset.py                 (563 usable strings)
scripts/audit_dataset.py      per-dataset health report
scripts/probe_duplicates.py   duplicate-structure analysis
scripts/peek_taxonomy.py      structural peek at python data modules
```