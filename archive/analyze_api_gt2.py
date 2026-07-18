import re
with open("api.js", "r", encoding="utf-8") as f:
    c = f.read()

# Search for gt2, fc/gt2, public_key API call patterns
for pattern in ["gt2", "/fc/", "public_key", "callback", "setupEnforcement", "userbrowser", "simulate"]:
    count = c.count(pattern)
    print(f"{pattern}: {count}")

# Find the actual API URL construction
print("\n=== gt2 URL construction ===")
# Look for the part that builds the gt2 URL
idx = c.find("/fc/gt2")
if idx >= 0:
    print(f"  Found '/fc/gt2' at position {idx}")
    print(f"  Context: {c[max(0,idx-200):idx+300]}")
else:
    # Try to find where callback query param is used
    idx = c.find("callback")
    if idx >= 0:
        ctx = c[max(0,idx-100):idx+200]
        if "gt2" in ctx or "fc" in ctx or "public" in ctx:
            print(f"  Found near 'callback': {ctx[:200]}")

# Search for where the URL is constructed with query params
print("\n=== Query param construction ===")
for pattern in ["public_key=", "userbrowser", "simulate="]:
    idx = c.find(pattern)
    if idx >= 0:
        print(f"  '{pattern}' at {idx}: {c[max(0,idx-50):idx+100]}")
