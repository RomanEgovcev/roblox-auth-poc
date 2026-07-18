"""Search for pU and oF functions in patched PX."""
import re

with open("main_min.js", "r", encoding="utf-8") as f:
    c = f.read()

# Search for pU function definition
# It should be something like "function pU(t){...}"
for m in re.finditer(r'function pU\([^)]+\)', c):
    pos = m.start()
    ctx = c[pos:pos+80]
    print(f"pU at {pos}: {ctx}")
    break

# Search for oF references (oF is called by pU)
# "ph=1,oF(t)" - search for this pattern
for m in re.finditer(r'ph=1,oF\(', c):
    pos = m.start()
    ctx = c[max(0, pos-30):pos+60]
    print(f"\noF call at {pos}: ...{ctx}...")
    break

# Search for oF function definition
for m in re.finditer(r'function oF\(', c):
    pos = m.start()
    ctx = c[pos:pos+80]
    print(f"\noF def at {pos}: {ctx}")
    break

# Search for what calls oF or sets ph
print(f"\n{'='*60}")
print(f"Searching for ph=1...")
for m in re.finditer(r'ph=1', c):
    pos = m.start()
    ctx = c[max(0, pos-30):pos+40]
    print(f"  at {pos}: ...{ctx}...")

print(f"\n{'='*60}")
print(f"Searching for oF(")
for m in re.finditer(r'oF\(', c):
    pos = m.start()
    ctx = c[max(0, pos-20):pos+40]
    print(f"  at {pos}: ...{ctx}...")

print(f"\n{'='*60}")
print(f"Searching for oC usage:")
for m in re.finditer(r'\boC\b', c):
    pos = m.start()
    ctx = c[max(0, pos-50):pos+60]
    # Filter out noise - only show unique contexts
    if pos < 100000 or (pos > 200000 and pos < 250000):  
        print(f"  at {pos}: ...{ctx}...")

print(f"\n{'='*60}")
print(f"Searching for oC= (assignment):")
for m in re.finditer(r'oC=', c):
    pos = m.start()
    ctx = c[max(0, pos-30):pos+30]
    print(f"  at {pos}: ...{ctx}...")
    
print(f"\n{'='*60}")
print(f"Searching for oC (non-assignment):")
for m in re.finditer(r'\boC\b(?!\s*=)', c):
    pos = m.start()
    ctx = c[max(0, pos-40):pos+50]
    if 66000 < pos < 74000:  # Focus near oF definition
        print(f"  at {pos}: ...{ctx}...")
