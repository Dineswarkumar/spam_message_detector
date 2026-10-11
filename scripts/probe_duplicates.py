"""
Deep probe on a duplicated dataset: find out whether the repeats carry any
information, or whether the row count is inflated by re-sampled metadata.

Usage:
    python scripts/probe_duplicates.py data/raw/needs_verification/ysangam_india_cyber_scam.csv
"""
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main():
    path = Path(sys.argv[1])
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    cols = list(rows[0].keys())
    text_col = next((c for c in cols if c.lower() in ("text", "message", "sms")), cols[0])
    label_col = next((c for c in cols if c.lower() in ("label", "class")), cols[1])

    print(f"rows: {len(rows):,}   columns: {cols}")

    # 1. Group by normalized text. How many unique texts, and does any single
    #    text carry BOTH labels? If yes the labels are noise.
    groups = defaultdict(list)
    for r in rows:
        key = " ".join((r.get(text_col) or "").lower().split())
        groups[key].append(r)

    print(f"\nunique texts: {len(groups):,}")
    conflict = [k for k, v in groups.items() if len({x[label_col] for x in v}) > 1]
    print(f"texts with CONFLICTING labels: {len(conflict):,}")

    # 2. Duplicate-group size distribution
    sizes = Counter(len(v) for v in groups.values())
    print(f"\nmultiplicity: {len(sizes)} distinct sizes")
    for n, c in sorted(sizes.items(), reverse=True)[:8]:
        print(f"  {n:>6,} rows share one text -> {c:,} distinct texts")

    # 3. Do the non-text columns actually vary within a duplicate group?
    meta = [c for c in cols if c not in (text_col, label_col)]
    print(f"\nwithin-group variation of metadata columns:")
    for c in meta:
        always_same = sum(
            1 for v in groups.values() if len({x.get(c, "") for x in v}) == 1
        )
        print(f"  {c:22} constant in {always_same:,}/{len(groups):,} groups "
              f"({always_same/len(groups)*100:.0f}%)")

    # 4. De-duplicate, then look at the class balance of what SURVIVES
    uniq_rows = [v[0] for v in groups.values()]
    lc = Counter(r[label_col] for r in uniq_rows)
    print(f"\nLABEL BALANCE AFTER DEDUPLICATION ({len(uniq_rows):,} unique):")
    for lab, n in lc.most_common():
        print(f"  {lab!r:8} {n:>6,}  ({n/len(uniq_rows)*100:5.1f}%)")

    # 5. Per-category breakdown on the deduplicated set
    cat_col = next((c for c in cols if "categor" in c.lower()), None)
    if cat_col:
        print(f"\nscam_category x label (deduplicated):")
        cross = defaultdict(Counter)
        for r in uniq_rows:
            cross[r.get(cat_col, "")][r[label_col]] += 1
        for cat, c in sorted(cross.items(), key=lambda kv: -sum(kv[1].values()))[:15]:
            print(f"  {cat[:34]:36} {dict(c)}")

    # 6. Length + language signal on the deduped set
    lens = sorted(len(r[text_col]) for r in uniq_rows)
    print(f"\nunique length chars: min={lens[0]} p50={lens[len(lens)//2]} "
          f"p95={lens[int(len(lens)*.95)]} max={lens[-1]}")

    # 7. Print a random-ish spread of unique texts so a human can eyeball quality
    print(f"\n{'='*70}\nSAMPLE OF UNIQUE TEXTS (every Nth, both labels):\n")
    step = max(1, len(uniq_rows) // 30)
    for r in uniq_rows[::step][:30]:
        print(f"  [{r[label_col]}] {r[text_col][:120]}")


if __name__ == "__main__":
    main()