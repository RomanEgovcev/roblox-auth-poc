import re
with open("enforcement_504897d1cd342e063d4f67d90600cf04.js", "r", encoding="utf-8") as f:
    c = f.read()

for pattern in ["postMessage", "message", "onmessage", "addEventListener", "session_token", "sessionToken", "public_key"]:
    count = c.count(pattern)
    print(f"{pattern}: {count}")

print("\n--- Session token refs ---")
for line in c.split(";"):
    if "session_token" in line or "sessionToken" in line:
        print("  " + line[:300])
        print()
