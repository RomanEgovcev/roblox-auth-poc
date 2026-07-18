"""Test gt2 API with correct params + get enforcement."""
import os, time, json, sys, requests, re

PUBLIC_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Origin': 'https://www.roblox.com',
    'Referer': 'https://www.roblox.com/',
}

# Step 1: Get gt2 response
print("[1] Calling gt2/public_key (GET)...", flush=True)
r = requests.get(
    f'https://arkoselabs.roblox.com/fc/gt2/public_key/{PUBLIC_KEY}',
    headers=headers,
    params={
        'callback': 'setupEnforcement0',
        'public_key': PUBLIC_KEY,
        'userbrowser': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'simulate': 'mouse',
    }
)
print(f"  Status: {r.status_code}", flush=True)
print(f"  Body: {r.text[:1000]}", flush=True)

# Extract session token
st = None
m = re.search(r'"session_token"\s*:\s*"([^"]+)"', r.text)
if m:
    st = m.group(1)
    print(f"\n  Session token: {st}", flush=True)
else:
    m2 = re.search(r'"token"\s*:\s*"([^"]+)"', r.text)
    if m2:
        st = m2.group(1)
        print(f"\n  Token: {st}", flush=True)

# Step 2: Try enforcement with no session (empty)
print("\n[2] Loading enforcement HTML (no session)...", flush=True)
r2 = requests.get(
    f'https://arkoselabs.roblox.com/v2/4.4.2/enforcement.504897d1cd342e063d4f67d90600cf04.html#{PUBLIC_KEY}&',
    headers=headers
)
print(f"  Status: {r2.status_code}", flush=True)
if r2.status_code == 200:
    print(f"  Body: {r2.text[:500]}", flush=True)

# Step 3: Try different enforcement hashes
print("\n[3] Trying different hashes...", flush=True)
for h in ['504897d1cd342e063d4f67d90600cf04', '162a14c47922edcced45ca4d9b28e5d5', 'current']:
    url = f'https://arkoselabs.roblox.com/v2/4.4.2/enforcement.{h}.html#{PUBLIC_KEY}&'
    r3 = requests.get(url, headers=headers)
    print(f"  {h}: {r3.status_code} ({len(r3.text)} bytes)", flush=True)

# Step 4: If session token found, try enforcement with it
if st:
    print(f"\n[4] Enforcement WITH session token...", flush=True)
    for h in ['504897d1cd342e063d4f67d90600cf04', '162a14c47922edcced45ca4d9b28e5d5']:
        url = f'https://arkoselabs.roblox.com/v2/4.4.2/enforcement.{h}.html#{PUBLIC_KEY}&{st}'
        r4 = requests.get(url, headers=headers)
        print(f"  {h}: {r4.status_code} ({len(r4.text)} bytes)", flush=True)
