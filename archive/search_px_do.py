"""Search PX main.min.js for 'do' field handling and collector response processing."""
import re

with open("main_min.js", "r", encoding="utf-8") as f:
    c = f.read()

# Find 'do' references
for m in re.finditer(r"['\"]do['\"]", c):
    pos = m.start()
    ctx = c[max(0, pos-60):pos+80]
    print(f"Pos {pos}: ...{ctx}...\n")
    if pos > 250000:
        break

print(f"\n{'='*60}\n")

# Also look for 'ob' references
for m in re.finditer(r"['\"]ob['\"]", c):
    pos = m.start()
    ctx = c[max(0, pos-60):pos+80]
    if pos < 100000 or pos > 190000:  # Only search in relevant range
        print(f"Pos {pos}: ...{ctx}...\n")
        if pos > 250000:
            break
