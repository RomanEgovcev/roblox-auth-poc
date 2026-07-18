"""Use Playwright API for challenge requests (bypass PX)."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Get cookies from the browser context
    ctx = page.context
    api = ctx.request
    
    # Get CSRF token via page-level fetch (this works)
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF: {csrf}", flush=True)
    
    if not csrf:
        print("No CSRF!", flush=True)
        browser.close()
        exit()
    
    # Try login with CSRF via Playwright API
    print(f"\n[1] Login POST via Playwright API...", flush=True)
    resp = api.post(
        "https://auth.roblox.com/v2/login",
        headers={
            "Content-Type": "application/json",
            "x-csrf-token": csrf,
        },
        data=json.dumps({
            "ctype": "Username",
            "cvalue": USER,
            "password": PASS,
        })
    )
    print(f"  Status: {resp.status}", flush=True)
    for k, v in resp.headers.items():
        if 'chall' in k.lower() or 'redemption' in k.lower() or 'csrf' in k.lower():
            print(f"  {k}: {v}", flush=True)
    
    chall_id = resp.headers.get('rblx-challenge-id', '')
    chall_type = resp.headers.get('rblx-challenge-type', '')
    chall_meta_b64 = resp.headers.get('rblx-challenge-metadata', '')
    
    print(f"  Challenge: {chall_id} ({chall_type})", flush=True)
    
    if chall_meta_b64:
        decoded = base64.b64decode(chall_meta_b64).decode()
        print(f"  Metadata: {decoded[:500]}", flush=True)
    
    # Try GET challenge details
    if chall_id:
        print(f"\n[2] GET challenge detail...", flush=True)
        resp2 = api.get(f"https://auth.roblox.com/v1/challenge/{chall_id}")
        print(f"  Status: {resp2.status}", flush=True)
        print(f"  Body: {resp2.text()[:500]}", flush=True)
        
        # Try POST empty solution
        print(f"\n[3] POST challenge solution...", flush=True)
        resp3 = api.post(
            f"https://auth.roblox.com/v1/challenge/{chall_id}",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "challengeId": chall_id,
                "challengeType": chall_type,
            })
        )
        print(f"  Status: {resp3.status}", flush=True)
        for k, v in resp3.headers.items():
            if 'chall' in k.lower() or 'token' in k.lower():
                print(f"  {k}: {v}", flush=True)
        print(f"  Body: {resp3.text()[:300]}", flush=True)
    
    time.sleep(2)
    browser.close()
