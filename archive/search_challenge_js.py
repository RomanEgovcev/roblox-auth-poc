"""Search Challenge.js for challenge handling logic."""
import re

with open("Challenge.js", "r", encoding="utf-8") as f:
    c = f.read()

# Find where challenge headers are read and processed
keywords = [
    'setupEnforcement', 'arkoseIframeId', 'funCaptchaPublicKeys',
    'rblx-challenge-id', 'rblx-challenge-type', 'rblx-challenge-metadata',
    'eligibleMethods', 'genericChallenge', 'challengeCompleted',
    'renderChallenge', 'proofOfWork', 'executedChallenge',
    'SET_CHALLENGE_COMPLETED', 'SHOW_MODAL_CHALLENGE',
    'ForceActionRedirect', 'handleChallenge',
    '/v1/challenge/', 'challengeVerify',
]

for kw in keywords:
    idx = c.find(kw)
    if idx >= 0:
        ctx = c[max(0, idx-150):idx+300]
        print(f"\n{'='*80}")
        print(f"KEYWORD: '{kw}' at offset {idx}")
        print(f"{'='*80}")
        print(ctx[:500])
        print()

# Also look for where the challenge type is checked/compared
print("\n\n===== CHALLENGE TYPE COMPARISONS =====")
for m in re.finditer(r'challengeType\s*(===|==)\s*["\']', c):
    pos = m.start()
    ctx = c[max(0, pos-100):pos+100]
    print(f"  at {pos}: ...{ctx}...")
