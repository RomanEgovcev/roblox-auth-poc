"""Intercept login POST to capture challenge response."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"
CAPTURED = {}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Intercept only /v2/login to read challenge headers
    def handle_login(route):
        url = route.request.url
        if '/v2/login' in url and route.request.method == 'POST':
            # Continue the request
            response = page.request.fetch(route.request)
            CAPTURED['login_status'] = response.status
            CAPTURED['login_headers'] = dict(response.headers)
            print(f"\n*** Login POST: {response.status} ***", flush=True)
            for k, v in response.headers.items():
                if 'chall' in k.lower() or 'token' in k.lower():
                    print(f"  {k}: {v}", flush=True)
            route.fulfill(status=response.status, headers=response.headers, body=response.body())
        else:
            route.continue_()
    
    page.route("https://auth.roblox.com/v2/login", handle_login)
    
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
    
    # Wait for challenge flow to complete
    time.sleep(10)
    
    if CAPTURED:
        print(f"\n\n=== Captured login response ===", flush=True)
        print(f"Status: {CAPTURED['login_status']}", flush=True)
        headers = CAPTURED.get('login_headers', {})
        chall_id = headers.get('rblx-challenge-id', '')
        chall_type = headers.get('rblx-challenge-type', '')
        chall_meta_b64 = headers.get('rblx-challenge-metadata', '')
        print(f"Challenge: {chall_id} ({chall_type})", flush=True)
        
        if chall_meta_b64:
            padded = chall_meta_b64 + '=' * (4 - len(chall_meta_b64) % 4) if len(chall_meta_b64) % 4 else chall_meta_b64
            meta = json.loads(base64.b64decode(padded).decode())
            print(f"Metadata: {json.dumps(meta, indent=2)}", flush=True)
            
            # Check if challenge has eligibleMethods
            sp = meta.get('sharedParameters', {})
            print(f"eligibleMethods: {sp.get('eligibleMethods')}", flush=True)
            
            # Check if redemption token was set after challenge handling
            rt = meta.get('redemptionToken', '')
            print(f"redemptionToken: '{rt}'", flush=True)
    
    # Check if we're still on login page
    time.sleep(3)
    print(f"\nFinal URL: {page.url}", flush=True)
    logged_in = 'login' not in page.url.lower()
    print(f"Logged in: {logged_in}", flush=True)
    
    time.sleep(2)
    browser.close()
