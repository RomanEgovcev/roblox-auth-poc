"""Direct Arkose API calls to get enforcement URL with real session."""
import os, time, json, base64, sys, requests

# Test direct API calls to Arkose
PUBLIC_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Step 1: Load api.js
print("[1] Loading api.js...", flush=True)
r = requests.get(
    f'https://arkoselabs.roblox.com/v2/{PUBLIC_KEY}/api.js',
    headers=headers
)
print(f"  Status: {r.status_code}, size: {len(r.text)}", flush=True)

# Step 2: Call settings API
print("\n[2] Calling settings API...", flush=True)
r2 = requests.get(
    f'https://arkoselabs.roblox.com/v2/{PUBLIC_KEY}/settings',
    headers=headers
)
print(f"  Status: {r2.status_code}", flush=True)
if r2.status_code == 200:
    print(f"  Body: {r2.text[:500]}", flush=True)

# Step 3: Call gt2/public_key API
print("\n[3] Calling gt2/public_key...", flush=True)
r3 = requests.post(
    f'https://arkoselabs.roblox.com/fc/gt2/public_key/{PUBLIC_KEY}',
    headers={**headers, 'Content-Type': 'application/x-www-form-urlencoded'},
    data='bda=9&callback=setupEnforcement0&public_key=476068BF-9607-4799-B53D-966BE98E2B81&userbrowser=Mozilla%2F5.0&simulate=mouse'
)
print(f"  Status: {r3.status_code}", flush=True)
if r3.status_code == 200:
    body = r3.text[:500]
    print(f"  Body: {body}", flush=True)
    if 'session_token' in r3.text:
        # Extract session token
        import re
        st_match = re.search(r'"session_token"\s*:\s*"([^"]+)"', r3.text)
        if st_match:
            print(f"  Session token: {st_match.group(1)}", flush=True)

# Step 4: Try enforcement HTML
print("\n[4] Loading enforcement HTML...", flush=True)
r4 = requests.get(
    f'https://arkoselabs.roblox.com/v2/4.4.2/enforcement.504897d1cd342e063d4f67d90600cf04.html#{PUBLIC_KEY}&',
    headers=headers
)
print(f"  Status: {r4.status_code}, size: {len(r4.text)}", flush=True)
if r4.status_code == 200:
    print(f"  Body: {r4.text[:500]}", flush=True)

# Step 5: Try fc/gfct
print("\n[5] Calling fc/gfct...", flush=True)
r5 = requests.get(
    f'https://arkoselabs.roblox.com/fc/gfct',
    headers=headers,
    params={'session': 'test', 'regpk': PUBLIC_KEY, 'regsurl': 'https://arkoselabs.roblox.com'}
)
print(f"  Status: {r5.status_code}", flush=True)
if r5.status_code == 200:
    print(f"  Body: {r5.text[:500]}", flush=True)
