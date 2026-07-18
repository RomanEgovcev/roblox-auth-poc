import re
with open("enforcement_504897d1cd342e063d4f67d90600cf04.js", "r", encoding="utf-8") as f:
    c = f.read()

# Find hash/URL related code
print("=== location.hash / URL parsing ===")
for line in c.split(";"):
    if "location" in line or "hash" in line.lower() or "public_key" in line or "session_token" in line or "sessionToken" in line:
        text = line.strip()
        if text:
            print(f"  {text[:300]}")
            print()
