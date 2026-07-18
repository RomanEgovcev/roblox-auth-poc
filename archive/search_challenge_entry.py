"""Find entry point for challenge handling after 403 response."""
import re

with open("Challenge.js", "r", encoding="utf-8") as f:
    c = f.read()

# Find where the challenge process starts
# Look for: handling the response, intercepting fetch/XHR
keywords = [
    'intercept', 'responseIntercept', 'requestIntercept',
    'axios', 'fetch', 'XMLHttpRequest', 'open', 'send',
    '/v2/login', 'auth.roblox', 'challengeFlow',
    'startChallenge', 'processChallenge', 'executeChallenge',
    'genericChallengeId', 'challengeId', 
    'challengeMetadata', 'challengeType',
    'PROOF_OF_WORK', 'PROOF_OF_SPACE',
    'Tm.',  # The enum pattern from earlier
]

for kw in keywords[:8]:  # Focus on response intercept
    idx = c.find(kw)
    if idx >= 0:
        ctx = c[max(0, idx-200):idx+300]
        print(f"\n{'='*80}")
        print(f"KEYWORD: '{kw}' at offset {idx}")
        print(f"{'='*80}")
        print(ctx[:500])
        print()

# Find Tm enum definition (challenge types)
idx = c.find("Tm.")
if idx >= 0:
    # Print all Tm properties
    start = idx
    end = c.find("};", start)
    if end > start:
        section = c[start:end+2]
        for m in re.finditer(r'Tm\.(\w+)=["\']([^"\']+)["\']', section):
            print(f"  Tm.{m.group(1)} = '{m.group(2)}'")

# Find where challenge type is switched/dispatched
print("\n\n===== CHALLENGE TYPE DISPATCHING =====")
# Look for switch statements
for m in re.finditer(r'switch\s*\(\s*\w+\s*\)\s*\{[^}]*challenge[^}]*\}', c, re.IGNORECASE):
    print(f"  at {m.start()}: ...{m.group()[:300]}...")
