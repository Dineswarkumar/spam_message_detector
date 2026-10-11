"""
Build data/processed/human_overrides.csv from the resolved annotation sheet.

Two sources of truth, both explicit:

  1. `spam` in the annotator's sheet means `scam` (confirmed by the annotator).
     That is a vocabulary normalisation, not a judgement change.

  2. The 49 CONFLICT rows and 23 blank rows are resolved here. Every override
     records WHY in `decision_basis` and is traceable to a review_id, so the
     resolution can be audited or reversed. Nothing is applied silently.

Output rows are keyed by normalized text, so build_corpus.py can join them
without depending on the blinded sheet's column layout.
"""
import csv
import pathlib
import sys
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHEET = ROOT / "data/annotation_blinded_145.csv"
OUT = ROOT / "data/processed/human_overrides.csv"

# Annotator confirmed: `spam` == `scam`.
VOCAB_FIX = {"spam": "scam", "": "", "legitimate": "legitimate",
             "marketing_spam": "marketing_spam"}

# ---------------------------------------------------------------------------
# Conflict resolutions. Each entry: review_id -> (final_label, basis)
# Only rows where the CONFLICT flag asserted a concrete different label get a
# final label. Where my reason said "arguable / defensible either way" the
# annotator's own label stands and no override is applied.
# ---------------------------------------------------------------------------
CONFLICT_DECISIONS = {
    # police / CBI / cybercrime impersonation -> scam
    "R135-946d24e655": ("scam", "police/blackmail impersonation"),
    "R136-ba7e54949b": ("scam", "police impersonation"),
    "R137-2fcec645ad": ("scam", "police impersonation"),
    "R138-b4b6361fae": ("scam", "police impersonation"),
    "R139-3ebac70821": ("scam", "police impersonation"),
    "R144-9db84d529e": ("scam", "legal-threat impersonation"),
    # guaranteed-return investment claim -> scam
    "R045-46a345aef2": ("scam", "guaranteed investment return"),
    "R046-46a345aef2": ("scam", "guaranteed investment return"),
    "R047-46a345aef2": ("scam", "guaranteed investment return"),
    "R048-46a345aef2": ("scam", "guaranteed investment return"),
    "R049-46a345aef2": ("scam", "guaranteed investment return"),
    # fake bank penalties / KYC takeover -> scam
    "R017-38bd913612": ("scam", "fake bank penalty demand"),
    "R077-f006672ecb": ("scam", "fake KYC account-takeover"),
    "R125-b3ae6a7ac7": ("scam", "credential harvesting via prize"),
    # prize / fee / recruitment advance-fee -> scam
    "R018-e4848e2571": ("scam", "recruitment advance fee"),
    "R035-81a3eeabdc": ("scam", "international prize advance fee"),
    "R053-10a18b5114": ("scam", "prize contingent on UPI payment"),
    "R085-ac0bc28709": ("scam", "free gift contingent on UPI fee"),
    "R093-273ebf8c5c": ("scam", "prize contingent on processing fee"),
    # commercial advertisements mislabelled legitimate -> marketing_spam
    "R030-61c36792f3": ("marketing_spam", "broadcast engagement solicitation"),
    "R099-f339c62193": ("marketing_spam", "commercial product advertisement"),
    "R103-360c05dc11": ("marketing_spam", "commercial service advertisement"),
    "R123-24ea5fcbee": ("marketing_spam", "debt-recovery pressure pattern"),
    # transactional confirmations mislabelled marketing_spam -> legitimate
    "R001-3aa8a6a9cb": ("legitimate", "registration confirmation"),
    "R002-145f6b31bf": ("legitimate", "platform activity notification"),
    "R003-286e86937a": ("legitimate", "financial NAV notification"),
    "R020-61083c9ceb": ("legitimate", "personal message, no solicitation"),
    # premium/adult/recruitment spam with no fraud mechanism -> marketing_spam
    "R068-ef48740117": ("marketing_spam", "carrier handset offer"),
    "R069-c7ff18b33a": ("marketing_spam", "adult premium spam"),
    "R073-e12a6e42e5": ("marketing_spam", "adult premium spam"),
    "R078-b12050383f": ("marketing_spam", "prize promo, no fee demanded"),
    "R100-9cffcdd077": ("marketing_spam", "no-fee prize marketing"),
    "R105-bdd9c0df19": ("marketing_spam", "recruitment marketing, no fee"),
    "R106-cc48c36f68": ("marketing_spam", "recruitment marketing, no fee"),
    "R107-2a6db45b7c": ("marketing_spam", "recruitment marketing, no fee"),
    "R108-2a6db45b7c": ("marketing_spam", "recruitment marketing, no fee"),
    "R109-2a6db45b7c": ("marketing_spam", "recruitment marketing, no fee"),
    "R116-3c8f8bcd6c": ("marketing_spam", "adult premium spam"),
    "R121-aec1d78cca": ("marketing_spam", "adult premium spam"),
    "R124-7616900a33": ("marketing_spam", "charity solicitation"),
    "R128-31339b33d3": ("marketing_spam", "carrier talktime offer"),
    "R129-51b9480b44": ("marketing_spam", "subscription promotion"),
}

# Blank rows: adopt the suggested label from the reason text.
# review_id -> (label, basis)
BLANK_DECISIONS = {
    "R004-ca7d4824f7": ("legitimate", "passive passport-ready notice"),
    "R010-4fbbb7f6c3": ("scam", "fake UIDAI update warning"),
    "R014-1e6e30d10f": ("scam", "PAN-Aadhaar penalty threat"),
    "R041-65d708f6a2": ("legitimate", "personal Telugu statement"),
    "R042-65d708f6a2": ("legitimate", "personal Telugu statement"),
    "R043-ffb617cf6d": ("legitimate", "personal Hindi statement"),
    "R050-ccc6572d50": ("scam", "Telugu prize-then-pay advance fee"),
    "R051-11396974a3": ("scam", "Telugu prize-then-pay advance fee"),
    "R056-90567c979f": ("scam", "Hindi prize plus OTP solicitation"),
    "R057-a7b07eedd3": ("scam", "Hindi prize plus OTP solicitation"),
    "R059-8b80875ed8": ("scam", "Hindi prize plus OTP solicitation"),
    "R074-8ae2ee91d2": ("marketing_spam", "prize promo via premium rate"),
    "R079-1b05b48f65": ("marketing_spam", "guaranteed prize promo"),
    "R081-4797aafa5e": ("legitimate", "Telugu card due-date reminder"),
    "R086-bd2c0a0645": ("scam", "Cyber Crime Dept impersonation"),
    "R088-fec9e5ca0d": ("scam", "relative-emergency UPI impersonation"),
    "R089-583fc99672": ("scam", "free gift contingent on UPI fee"),
    "R090-207c483d47": ("scam", "fake customs hold plus payment demand"),
    "R092-3634aa41f4": ("scam", "UIDAI impersonation asking OTP"),
    "R094-e4cd09ad70": ("scam", "money-laundering net-banking threat"),
    "R101-79f5ac0a5d": ("marketing_spam", "bulk SMS package advertisement"),
    "R102-b97c1d52d9": ("marketing_spam", "no-fee prize marketing"),
    "R104-9f425e84aa": ("marketing_spam", "real-estate advertisement"),
}

# Conflict rows where the annotator's label was called "arguable / defensible".
# No override applied -- the annotator's judgement stands.
NO_OVERRIDE_ARGUEABLE = {
    "R005-37ef2a825f", "R007-d913294358", "R008-30755dff0e",
    "R009-13fb917f00", "R065-e514441973", "R075-7b5e4a550a",
    "R127-a800514879",
}


def norm(t):
    return " ".join((t or "").lower().split())


def main():
    rows = list(csv.DictReader(SHEET.open(encoding="utf-8-sig", newline="")))

    applied = []
    stats = Counter()

    for r in rows:
        rid = r["review_id"]
        annot = (r["human_label"] or "").strip()
        base = VOCAB_FIX.get(annot)

        if rid in CONFLICT_DECISIONS:
            final, basis = CONFLICT_DECISIONS[rid]
            kind = "conflict_resolved"
            stats["conflict_resolved"] += 1
        elif rid in BLANK_DECISIONS:
            final, basis = BLANK_DECISIONS[rid]
            kind = "blank_filled"
            stats["blank_filled"] += 1
        elif rid in NO_OVERRIDE_ARGUEABLE:
            final, basis = base, "arguable; annotator label stands"
            kind = "no_override"
            stats["no_override"] += 1
        else:
            final, basis = base, "annotator label"
            kind = "as_labelled"
            stats["as_labelled"] += 1

        if not final:
            continue

        applied.append({
            "review_id": rid,
            "text_norm": norm(r["text"]),
            "annotator_label": annot,
            "override_label": final,
            "decision_kind": kind,
            "decision_basis": basis,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(applied[0].keys()))
        w.writeheader()
        w.writerows(applied)

    print(f"wrote {OUT}  ({len(applied)} override rows)")
    print(f"  as_labelled       : {stats['as_labelled']}")
    print(f"  conflict_resolved : {stats['conflict_resolved']}")
    print(f"  blank_filled      : {stats['blank_filled']}")
    print(f"  no_override       : {stats['no_override']}")
    print(f"\n  override changed label: "
          f"{sum(1 for a in applied if a['annotator_label'] and VOCAB_FIX.get(a['annotator_label']) != a['override_label'])}")
    print(f"  spam->scam normalisation: "
          f"{sum(1 for a in applied if a['annotator_label'] == 'spam')}")

    missing = set(CONFLICT_DECISIONS) | set(BLANK_DECISIONS) | NO_OVERRIDE_ARGUEABLE
    ids = {r["review_id"] for r in rows}
    gap = missing - ids
    if gap:
        print(f"\nERROR: {len(gap)} decision ids not present in sheet: {sorted(gap)}")
        sys.exit(1)
    print("  all decision ids matched the sheet")


if __name__ == "__main__":
    main()