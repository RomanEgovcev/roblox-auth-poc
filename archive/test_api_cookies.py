"""Use Playwright API with cookies from browser context."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    context = browser.new_context()
    page = context.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Get CSRF token via page fetch
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF: {csrf}", flush=True)
    
    # Get cookies from context
    cookies = context.cookies()
    cookie_jar = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
    print(f"Cookies: {cookie_jar[:100]}...", flush=True)
    
    # Use Playwright API with cookies
    api = context.request
    
    # Login with CSRF via Playwright API (now with cookies from context)
    resp = api.post(
        "https://auth.roblox.com/v2/login",
        headers={
            "Content-Type": "application/json",
            "x-csrf-token": csrf,
            "Cookie": cookie_jar,
        },
        data=json.dumps({
            "ctype": "Username",
            "cvalue": USER,
            "password": PASS,
        })
    )
    print(f"\n[1] Playwright API login:", flush=True)
    print(f"  Status: {resp.status}", flush=True)
    
    chall_id = resp.headers.get('rblx-challenge-id', '')
    chall_type = resp.headers.get('rblx-challenge-type', '')
    chall_meta_b64 = resp.headers.get('rblx-challenge-metadata', '')
    print(f"  Challenge: {chall_id} ({chall_type})", flush=True)
    
    if chall_meta_b64:
        decoded = base64.b64decode(chall_meta_b64).decode()
        meta = json.loads(decoded)
        sp = meta.get('sharedParameters', {})
        print(f"  eligibleMethods: {sp.get('eligibleMethods')}", flush=True)
    
    # Try GET challenge
    if chall_id:
        resp2 = api.get(f"https://auth.roblox.com/v1/challenge/{chall_id}",
            headers={"Cookie": cookie_jar})
        print(f"\n[2] GET challenge: {resp2.status}", flush=True)
        print(f"  {resp2.text()[:500]}", flush=True)
        
        # Try POST empty solution
        resp3 = api.post(
            f"https://auth.roblox.com/v1/challenge/{chall_id}",
            headers={
                "Content-Type": "application/json",
                "Cookie": cookie_jar,
            },
            data=json.dumps({
                "challengeId": chall_id,
                "challengeType": chall_type,
            })
        )
        print(f"\n[3] POST solution: {resp3.status}", flush=True)
        for k, v in resp3.headers.items():
            print(f"  {k}: {v}", flush=True)
        print(f"  Body: {resp3.text()[:500]}", flush=True)
    
    time.sleep(2)
    browser.close()
