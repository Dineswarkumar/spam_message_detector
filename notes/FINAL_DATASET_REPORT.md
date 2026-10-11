# Final Dataset Report — All Sources Audited

Date: 2026-10-09
Terminology note: **Tenglish** = Telugu written in Roman letters (not "Tanglish").

All numbers measured with `scripts/audit_dataset.py`, `scripts/probe_duplicates.py`,
`scripts/check_overlap.py` and `scripts/language_coverage.py`. Nothing here is
taken from a dataset README.

---

## 1. Verification of the two URLs

### `shshnk158/Multilingual-SMS-spam-detection-using-RNN` ✅ verified — the dataset is present

The repo is a **fork** of `manohar9600/SMS-Spam-Classification-on-Indian-Dataset...`
and its `indian_spam.csv` is that same file. You already downloaded it — it is in
`dataset/-SMS-Spam-Classification-on-Indian-Dataset-...-main/indian_spam.csv`.

Provenance: **Yadav, Kumaraguru, Goyal, Gupta & Naik (2011)**, crowdsourced via the
IIIT Delhi Precog requester portal. 43 participants contributed real SMS.
**This is the only genuinely human-collected Indian-language data we have.**

⚠️ The README contains an unrelated line about "New York taxi demand prediction".
That is boilerplate contamination from a template repo, not a description of this
dataset. Ignore it.

### `aclanthology.org/2021.ranlp-1.85` ✅ read — no dataset, but confirms our direction

RANLP 2021, *"A Neural Language Model for Unsupervised Task-Oriented Dialog for
Indian Languages"* region. Its relevant contribution: **unsupervised task-oriented
dialog for Indian languages**, using **romanized ("transliterated") input** for
English/Hindi/Telugu so one model serves all three. Reported a ~60% error
reduction against monolingual baselines.

This independently validates two decisions we already made:
1. Romanized (Hinglish/Tenglish) text matters as a first-class input format.
2. One multilingual model beats per-language models.

It is **not a spam dataset** — no rows to download, so no change to our corpus.

---

## 2. `indian_spam.csv` — the best Indian dataset we have

```
rows:          2,000  (1,000 ham / 1,000 spam, 50/50)
unique:        1,970  (only 30 duplicates, 1.5%)
script:        100% Latin
Hinglish:      87 rows (4.3%)
length:        p50 148, p95 287, max 2007 chars
```

**Quality is excellent.** 1.5% duplicates is the lowest of any dataset we have
seen. Human-written, natural, messy, with real typos and real-world phrasing —
unlike our synthetic data.

**Two corrections to the name:**

1. Despite "Hindi and English" in the title, it contains **zero Devanagari
   script**. It is English plus Romanized Hindi. Do not describe it as covering
   Hindi script.
2. **Telugu: 0 rows.** Not one Telugu message in the dataset named after this
   domain.

**It is spam, not scam.** This is the most important distinction. The samples are:

- quiz-show promotion ("reply 1 for Horoscope, 2 for Suvichar...")
- IEEE project offers, real-estate ads, TV channel promos
- generic bulk marketing

**There are no bank-OTP lures, no police impersonation, no UPI fraud, no digital
arrest.** That is a different target class from what we're trying to detect.
Merging it into training without care will teach the model that *bulk marketing
= fraud*, which pushes precision the wrong way and leaves our actual scam
category unlearned.

**Do these two feature-separation rates hold up:**

| feature | spam | ham | ratio |
|---|---|---|---|
| contains URL | 13.2% | 0.1% | 132× |
| 10-digit phone | 20.4% | 0.2% | 102× |
| 4–6 digit number | 35.7% | 2.9% | 12× |
| rupee amount | 56.6% | 18.0% | 3.1× |

URL and phone number are strong signals. The rupee signal is weak — 18% of ham
mentions money, because this ham set is full of people discussing personal
finance and jokes.

**Zero overlap with UCI** — measured: 1 shared message out of 1,970. So it adds
**1,969 genuinely new rows**, all unique to our corpus. That's the single largest
honest gain available right now.

---

## 3. Complete dataset inventory

| # | Dataset | Location | Rows | **Unique** | Dup % | Verdict |
|---|---|---|---|---|---|---|
| 1 | UCI SMS Spam | `01_uci_sms_spam/` | 5,572 | 5,159 | 0% | ✅ core English |
| 2 | **Indian crowdsourced 2011** | `-SMS-Spam-...-main/` | 2,000 | **1,970** | **1.5%** | ✅ **best Indian** |
| 3 | SMS Phishing 5971 | `SMS PHISHING.../` | 5,971 | 5,831 | 2.3% | ✅ smishing split; 84% dup of UCI |
| 4 | Atharva taxonomy | `04_phishing_taxonomy_atharva/` | 605 | 563 | 7% | ✅ real multilingual |
| 5 | ysangam | `03_needs_verification/` | 10,000 | **743** | **92.6%** | ⚠️ taxonomy only |
| 6 | legacy multilingual | `02_legacy_old_repo.../` | 600 | **232** | **61.3%** | ⚠️ salvage uniques |
| 7 | legacy merged | `02_legacy_old_repo.../` | 6,172 | — | — | ❌ UCI dup, 97.6% Latin |
| 8 | karanverma19 | `03_needs_verification/` | 120 | **49** | **59.2%** | ❌ reject |
| 9 | uniquedata | `uniquedata/` | **25** | 25 | — | ❌ reject (card claims 10k–100k) |

### Overlap map (measured, not assumed)

- `Dataset_5971` ∩ UCI = **4,886** → only **945 new** messages
- `indian_spam` ∩ UCI = **1** → **1,969 new**
- legacy `dataset.csv` is a **superset of UCI** → contributes ~0 new beyond #6

---

## 4. Real language coverage — the honest picture

Deduped, pooled across every real source:

| Language | Real unique | Change since last report |
|---|---|---|
| English | **18,912** | +7,038 (the Indian dataset) |
| Hinglish | **825** | +64 |
| **Devanagari (Hindi)** | **154** | unchanged |
| **Telugu** | **78** | unchanged |
| **Tenglish** | **1** | unchanged |

**Correcting my own earlier numbers:** I previously said Hindi was "~180 unique".
That was counted from the merged `dataset.csv`, which double-counts the legacy
multilingual file. True deduplicated Devanagari is **154**. I was also wrong to
imply Telugu was usable — it is **78 rows**, all from one 33 KB legacy file.

Synthetic support (12,000 generated rows, ~3,000 per language) exists for
`en / hinglish / hi / te`. **There is no Tenglish generation at all** — that is a
real hole, and correcting my own earlier terminology: it is **Tenglish**.

---

## 5. Corrected total corpus

| | Unique real messages |
|---|---|
| Before this report | ~7,642 |
| **Now (after `indian_spam.csv`)** | **~9,611** |

Of which:
- English + smishing: ~8,104
- Hinglish: 825
- Devanagari: 154
- Telugu: 78
- Tenglish: 1

**The multilingual axis is still the weak one.** One good Indian dataset moved
English volume, not Indian-language volume. Hindi, Telugu and Tenglish together
remain **233 real messages**.

---

## 6. Actions to take on `indian_spam.csv`

**Do:** use it. Highest-quality human Indian data we have, zero UCI overlap,
strong URL/phone signal separation.

**Handle the class-mismatch explicitly.** Its `spam` = bulk marketing. Our
`scam` = fraud. Options:
- (a) train a **three-class** head: `legit / marketing-spam / scam` — most
  honest, most impressive, matches the RANLP-style multi-task framing
- (b) keep binary but exclude it from scam-specific evaluation, and report its
  metrics separately

Option (a) is the better project. It also means `Dataset_5971`'s
smishing/spam/ham split (already downloaded) falls into place naturally.

---

## 7. What we still do not have

1. **Any real Hindi script at scale** — 154 rows.
2. **Any Telugu at all** — 78 rows, one legacy file.
3. **Any Tenglish** — 1 row.
4. **Real Indian transactional SMS (hard negatives)** — still zero. This remains
   the single biggest risk to the project.

Our synthetic generator covers items 1–3 structurally, but from 12 templates
each, written by me rather than collected. State that plainly in the writeup.

---

## 8. Folder layout after consolidation

All sources now under `dataset/`:

```
dataset/
  01_uci_sms_spam/                    UCI (SMSSpamCollection + readme)
  02_legacy_old_repo_rakshasutra/     spam.csv, dataset.csv, multilingual_fraud_dataset.csv
  03_needs_verification/              ysangam 10k, karanverma19
  04_phishing_taxonomy_atharva/       atharva_dataset.py
  sms/                                original UCI download (redundant with 01)
  SMS PHISHING DATASET.../            Dataset_5971 + extract scripts + pdfs
  uniquedata/                         REJECTED, 25 rows + 25 images
  -SMS-Spam-...-Indian-Dataset-main/  indian_spam.csv  ← the new one
```

Generated artefacts stay separate from raw data:
```
data/synthetic/synthetic_sms.csv      12,000 generated rows
data/processed/synthetic_train.csv    8,953  (grouped split)
data/processed/synthetic_test.csv     3,047  (100% unseen templates)
data/interim/                         uci_sms.csv, grounded_sources.json
```

---

## 9. Reproduction

```powershell
python scripts/audit_dataset.py    dataset/.../indian_spam.csv
python scripts/language_coverage.py          # per-language totals, all sources
python scripts/check_overlap.py data/interim/uci_sms.csv text label \
       "dataset/SMS PHISHING DATASET.../Dataset_5971.csv" TEXT LABEL
python scripts/probe_duplicates.py dataset/03_needs_verification/ysangam_india_cyber_scam.csv
```