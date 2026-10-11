"""Quick structural look at the Atharva taxonomy dataset (a Python data module)."""
import collections
import pathlib
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

p = pathlib.Path(sys.argv[1])
src = p.read_text(encoding="utf-8", errors="replace")

print(f"size: {len(src):,} chars   lines: {src.count(chr(10)):,}")

# Assign the list variable name(s) that hold message records.
names = re.findall(r"^\s*([A-Z_a-z][A-Za-z0-9_]*)\s*=\s*[\[\{]", src, re.M)
print(f"module-level containers: {names}")

lits = re.findall(r"""["']([^"']{4,90})["']""", src)
c = collections.Counter(lits)
print(f"\nstring literals: {len(lits):,}   distinct: {len(c):,}\n")
print("most repeated literals (template-filler signal):")
for k, n in c.most_common(20):
    print(f"  {n:4}  {k[:80]}")

# How many distinct message-looking strings?
msgs = [l for l in lits if len(l.split()) >= 3]
print(f"\nstrings with >=3 words: {len(msgs):,}   distinct: {len(set(msgs)):,}")
print("\nsample:")
for m in sorted(set(msgs))[:25]:
    print(f"  {m[:100]}")

cats = sorted({l for l in lits if l.islower() and "_" in l and " " not in l})
print(f"\npossible category names ({len(cats)}):")
for c_ in cats[:40]:
    print(f"  {c_}")