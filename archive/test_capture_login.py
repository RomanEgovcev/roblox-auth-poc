"""Read login response body directly via page.on('response')."""
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
    
    login_responses = []
    page.on("response", lambda r: login_responses.append(r) if '/v2/login' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    page.evaluate(f"""() => {{
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        const u = document.getElementById('login-username');
        const p = document.getElementById('login-password');
        if (u) {{ setter.call(u, '{USER}'); u.dispatchEvent(new Event('input', {{bubbles: true}})); }}
        if (p) {{ setter.call(p, '{PASS}'); p.dispatchEvent(new Event('input', {{bubbles: true}})); }}
    }}""")
    time.sleep(1)
    
    page.click('.login-button', timeout=5000)
    
    # Wait for challenge flow and retry
    for i in range(15):
        time.sleep(2)
        for r in login_responses:
            if not hasattr(r, '_read'):
                r._read = True
                print(f"\n[Login response] POST #{len([x for x in login_responses if hasattr(x, '_read')])}", flush=True)
                print(f"  Status: {r.status}", flush=True)
                # Headers
                chall_id = r.headers.get('rblx-challenge-id', '')
                chall_type = r.headers.get('rblx-challenge-type', '')
                chall_meta = r.headers.get('rblx-challenge-metadata', '')
                csrf = r.headers.get('x-csrf-token', '')
                if chall_id:
                    print(f"  Challenge: {chall_id} ({chall_type})", flush=True)
                if csrf:
                    print(f"  CSRF: {csrf}", flush=True)
                if chall_meta:
                    try:
                        meta = json.loads(base64.b64decode(chall_meta + '==').decode())
                        print(f"  eligibleMethods: {meta.get('sharedParameters', {}).get('eligibleMethods')}", flush=True)
                        print(f"  redemptionToken: '{meta.get('redemptionToken', '')}'", flush=True)
                    except:
                        print(f"  Metadata: {chall_meta[:80]}...", flush=True)
                try:
                    body = r.text()[:300]
                    if body:
                        print(f"  Body: {body}", flush=True)
                except:
                    pass
    
    print(f"\nFinal URL: {page.url}", flush=True)
    logged_in = '/login' not in page.url and 'login' not in page.url.lower()
    print(f"Logged in: {logged_in}", flush=True)
    
    time.sleep(2)
    browser.close()
