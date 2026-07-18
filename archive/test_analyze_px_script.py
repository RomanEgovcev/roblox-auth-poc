"""Download and analyze PX main.min.js to find the eval issue."""
import os, time, json, requests

# Fetch the actual PX script
url = "https://client.px-cloud.net/PXbf8PROpW/main.min.js"
resp = requests.get(url, timeout=30)
print(f"Status: {resp.status_code}, Size: {len(resp.content)} bytes", flush=True)

content = resp.text
# Look for eval patterns
import re

# Find all eval/new Function calls
evals = [(m.start(), content[max(0,m.start()-100):m.end()+100]) for m in re.finditer(r'\beval\s*\(', content)]
functions = [(m.start(), content[max(0,m.start()-100):m.end()+100]) for m in re.finditer(r'new\s+Function\s*\(', content)]

print(f"\nEval calls: {len(evals)}", flush=True)
for pos, ctx in evals[:5]:
    print(f"  @{pos}: ...{ctx}...", flush=True)

print(f"\nNew Function calls: {len(functions)}", flush=True)
for pos, ctx in functions[:5]:
    print(f"  @{pos}: ...{ctx}...", flush=True)

# Find the EvalError location
# Error was at: mJ (main.min.js:2:66532)
error_pos = 66531  # 0-indexed
print(f"\n--- Context around column 66532 ---", flush=True)
print(content[65531:67532], flush=True)

# Also check around the other error locations
for col in [73633, 232149, 231767]:
    print(f"\n--- Context around column {col+1} ---", flush=True)
    print(content[max(0,col-100):col+100], flush=True)

# Save for analysis
with open("main_min.js", "w", encoding="utf-8") as f:
    f.write(content)
print("\nSaved to main_min.js", flush=True)
