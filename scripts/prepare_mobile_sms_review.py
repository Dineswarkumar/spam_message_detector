"""Create a locally redacted review sheet from an SMS Backup & Restore XML.

Reads the newest ``data/raw/sms-*.xml`` by default and writes a CSV worksheet
to ``data/processed/mobile_sms_review.csv``. Message labels are deliberately
left blank for human review. The input XML is never modified and message text
is never printed.

This is a first-pass privacy filter, not a guarantee of anonymisation. Review
every row locally before using it, especially for names or details written as
words rather than numbers.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "data" / "raw"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "mobile_sms_review.csv"


def redact(text: str) -> str:
    """Replace common personal, financial, and authentication identifiers."""
    text = text or ""
    text = re.sub(r"(?i)\bhttps?://\S+|\bwww\.\S+", "[URL]", text)
    text = re.sub(
        r"(?i)\b(?:[a-z0-9-]+\.)+(?:com|in|net|org|co|io|info|xyz)(?:/\S*)?",
        "[URL]",
        text,
    )
    # Includes UPI handles such as name@bank, not only email addresses.
    text = re.sub(r"(?i)\b[\w.+-]+@[\w.-]+\b", "[ID]", text)
    # Phone-like sequences, including Indian country-code formatting.
    text = re.sub(r"(?<!\w)(?:\+?\d[\s().-]*){10,13}(?!\w)", "[PHONE]", text)
    # Salutations often include the recipient's name in bank messages.
    text = re.sub(
        r"(?i)\b(dear|hello|hi|प्रिय)\s+[^\s,!.?;:]{2,40}",
        r"\1 [NAME]",
        text,
    )
    # Mask transaction counterparties; these names are not needed for the SMS template.
    text = re.sub(
        r"(?i)\bto\s+(.{1,60}?)(?=\s*,?\s*UPI\s*(?:Ref|:|ID)?\b)",
        "to [PARTY]",
        text,
    )
    text = re.sub(
        r"(?i)\bfrom\s+(?!a/c\b|account\b)(.{1,60}?)(?=\s*[;,]\s*UPI\s*:?)",
        "from [PARTY]",
        text,
    )
    # Mask account/card identifiers, including short visible suffixes.
    text = re.sub(
        r"(?i)\b(a/c|acct|account)\s*(?:no\.?\s*)?(?:[x*]*\d+[a-z0-9]*|[a-z0-9]*\d{3,}[a-z0-9]*)",
        r"\1 [ACCOUNT]",
        text,
    )
    text = re.sub(r"(?i)\b(card ending|ending)\s*[x*\d]+", r"\1 [CARD]", text)
    # Replace dates/times as whole tokens, so repeat notices become one template.
    text = re.sub(r"(?i)\b\d{1,2}[-/]?[a-z]{3}[-/]?\d{2,4}\b", "[DATE]", text)
    text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\b", "[TIME]", text, flags=re.I)
    # Currency values are variable personal transaction details.
    text = re.sub(r"(?i)(₹|\b(?:rs\.?|inr)\s*)\s*\d+(?:,\d{2,3})*(?:\.\d{1,2})?", r"\1[AMOUNT]", text)
    # Mixed letter/number transaction or device reference IDs.
    text = re.sub(r"\b(?=[A-Z0-9]*\d)[A-Z0-9]{6,}\b", "[REF]", text, flags=re.I)
    # Redact remaining long numbers, including digits embedded in reference IDs.
    text = re.sub(r"\d(?:[\d ,./-]*\d)?", _redact_number_run, text)
    return re.sub(r"\s+", " ", text).strip()


def _redact_number_run(match: re.Match[str]) -> str:
    value = match.group(0)
    digits = re.sub(r"\D", "", value)
    return "[NUMBER]" if len(digits) >= 4 else value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="XML export; defaults to newest data/raw/sms-*.xml")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    candidates = [args.input] if args.input else sorted(
        DEFAULT_INPUT_DIR.glob("sms-*.xml"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not candidates or not candidates[0].is_file():
        print("No SMS XML export found in data/raw. Copy it there or pass --input.", file=sys.stderr)
        return 2

    xml_path = candidates[0]
    root = ET.parse(xml_path).getroot()
    received = [node for node in root.findall("sms") if node.get("type") == "1"]
    sender_ids: dict[str, str] = {}
    deduped: dict[str, dict[str, str | int]] = {}

    for node in received:
        safe_text = redact(node.get("body", ""))
        if not safe_text:
            continue
        sender = node.get("address", "")
        if sender and sender not in sender_ids:
            sender_ids[sender] = f"sender_{len(sender_ids) + 1:03d}"
        alias = sender_ids.get(sender, "sender_unknown")
        # Canonicalize punctuation/case after privacy substitutions. This groups
        # repeated message templates despite spacing or punctuation differences.
        key = re.sub(r"[^\w\[\]]+", " ", safe_text.casefold(), flags=re.UNICODE).strip()
        if key in deduped:
            deduped[key]["duplicate_count"] = int(deduped[key]["duplicate_count"]) + 1
            continue
        deduped[key] = {
            "message_id": len(deduped) + 1,
            "sender_group": alias,
            "text_redacted": safe_text,
            "duplicate_count": 1,
            "label": "",
            "review_notes": "",
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["message_id", "sender_group", "text_redacted", "duplicate_count", "label", "review_notes"]
    with args.output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(deduped.values())

    skipped = len(root.findall("mms"))
    print(f"Input XML: {xml_path.name}")
    print(f"Incoming SMS: {len(received)}; unique redacted messages: {len(deduped)}")
    print(f"Skipped MMS records: {skipped}")
    print(f"Review sheet: {args.output}")
    print("Labels are blank. Check every row locally for any personal details the automatic filter missed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
