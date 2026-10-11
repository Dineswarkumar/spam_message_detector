# Synthetic Generation — Grounding & Methodology

Date: 2026-10-09

## The question this answers

> "on what basis will you make synthetic generation? you can't just do random things"

Right. Random generation produces text with no relationship to reality, and a
model trained on it learns nothing. Everything below is mined from the audited
real corpora. `scripts/extract_grounding.py` runs first and emits
`data/interim/grounded_sources.json`; the generator reads only from that.

## Three sources of grounding

**1. Scam structure — from `ysangam`, deduplicated to 743 unique.**
Six categories that genuinely exist in Indian fraud data, with the vocabulary
that co-occurs with each. Measured, not assumed:

| category | distinct words observed |
|---|---|
| `police_digital_arrest` | 101 |
| `police_blackmail` | 75 |
| `bank_kyc` | 65 |
| `relative` | 58 |
| `lottery` | 57 |
| `amazon` | 53 |
| `aadhaar` | 51 |

⚠️ **Caveat found during extraction:** these six categories share nearly
identical top-vocabulary (`raha`, `hoon`, `aapke`, `aapka`, `turant`, `dena`,
`hoga`, `kijiye` appear across all of them). That is further evidence of
template generation in the source. It does not invalidate the *categories* —
they are real fraud types — but it means we must NOT treat their vocabularies
as independent signals. Our templates therefore differentiate categories by
*scenario and threat* (police investigation vs bank closure vs prize claim),
not by borrowing their word lists.

**2. Entities — only names actually observed in the real corpora.**
Measured co-occurrence: `Police` 99, `Vi` 135, `WhatsApp` 49, `Amazon` 29,
`TRAI` 13, `RBI` 6, `UIDAI` 2, `EPFO` 1. Nothing invented.

**3. Legitimate phrasing — from the 250 real Atharva `LEGIT_MESSAGES`**
(delivery confirmations, appointment reminders, ride alerts, bill dues) plus
real bank transactional formats (OTP, UPI alert, salary credit, autopay).

## The design decision that matters most

**The hard negatives deliberately reuse the scam vocabulary.**

Look at the pairs:

| scam template | legit template |
|---|---|
| `sa11` card **blocked** due to failed KYC, pay reactivation charge | `lg16` KYC due for renewal, submit at branch |
| `sa03` account **closed** in 24h unless KYC updated at URL | `lg15` account **restricted** for security, no money debited |
| `sa09` don't switch off phone, OTP will be sent | `lg01` your OTP is 456789, don't share it |
| `sa06` parcel held at customs, pay clearance | `lg04` order out for delivery |

A model that learns "blocked / KYC / OTP / verification = scam" will be wrong
on every one of the `lg` rows. **This is deliberate.** Those are the messages
that decide whether the model flags every bank OTP in the country — the exact
failure mode of the old project, where no hard negatives existed at all.

For scale: the old legacy multilingual file had 232 unique messages, all of
them trivial greetings. We now have ~4,500 legit transactional rows that
contain the same scary keywords as the scams.

## Three axes of variation

Chosen because they are what actually varies in real scam traffic:

1. **template** — the scenario (28 templates: 12 scam, 16 legit)
2. **slot fill** — entity, amount, OTP, UPI ID, URL, account, date
3. **rendering** — `en` / `hinglish` / `hi` (Devanagari) / `te` (Telugu)

Each scenario is written four times, once per language. A fraudster sends the
same threat in whichever script the victim reads — so this mirrors reality
rather than inflating counts.

## Result

```
12,000 rows | 28 templates | 11,409 unique texts
label:  6,000 scam / 6,000 legit
lang:   en 2,984 | hinglish 2,992 | hi 3,018 | te 3,006
```

## Leakage control — the whole point

Every row carries `template_id`. Splits MUST group on it. `scripts/build_splits.py`
proves what happens otherwise:

```
RANDOM split (the default, and the mistake)
  template_id shared train<->test: 28 of 28
  test rows whose template was NEVER in training: 0 / 2,400  (0.0%)

GROUPED split (grouped by template_id, stratified by label)
  template_id shared train<->test: 0
  test rows whose template was NEVER in training: 3,047 / 3,047  (100.0%)
```

With a random split, **every single test message came from a template the model
already memorised.** The score measures memorisation, not generalisation. This
is the trap that produces impressive-looking fake numbers, and it is why the
grouped split is non-negotiable.

Split balance after stratification:
```
train  8,953   scam 4,472 / legit 4,481
test   3,047   scam 1,528 / legit 1,519
test per-language:  hi 773 | hinglish 778 | en 731 | te 765
```

Stratification is applied per label, otherwise grouping by template inherits the
template mix and the test set skews (the unstratified run gave 74% scam, which
makes precision/recall unreadable).

## Honest limitations — state these in your writeup

1. **28 templates is not many.** The grouped-split test set contains 14 unseen
   templates per class. It measures generalisation across 14 scenarios, which is
   real but narrow. Do not claim more than that.
2. **Slot-filled data is easier than real text.** Real SMS has typos, truncated
   messages, sender IDs, mixed punctuation. Ours is clean prose.
3. **Class balance is 50/50.** Real SMS traffic is roughly 85–90% legitimate.
   Report metrics at realistic skew separately or the precision number is
   misleading.
4. **The `lang` field is our own label, not detected.** Real inference will see
   code-mixed text inside one message; our templates keep one language per row.
5. **This does not replace real data.** It closes the volume gap while the real
   Hindi/Hinglish hard-negative collection continues.

## Scripts

```
scripts/extract_grounding.py   mines vocabulary/entities/patterns from real sources
scripts/generate_synthetic.py  template-based generator, emits template_id
scripts/build_splits.py        proves leakage, writes grouped+stratified splits
scripts/audit_dataset.py       reuse on the generated file
```

## Commands

```powershell
python scripts/extract_grounding.py
python scripts/generate_synthetic.py --n-scam 6000 --n-legit 6000 --seed 42
python scripts/build_splits.py
python scripts/audit_dataset.py data/synthetic/synthetic_sms.csv
```