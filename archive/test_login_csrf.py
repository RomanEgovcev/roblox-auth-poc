"""Full login flow with XSRF token to trigger challenge."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    def log_resp(r):
        url = r.url
        if any(x in url for x in ['auth.roblox.com', 'collector', 'arkoselabs', 'api.js', 'enforcement', 'game-core']):
            print(f"  [{r.status}] {url[40:140]}", flush=True)
    
    page.on("response", log_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Step 1: Login POST to get CSRF token
    print(f"\n[1] Login POST without CSRF...", flush=True)
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST',
            credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                ctype: 'Username',
                cvalue: '{USER}',
                password: '{PASS}',
            }}),
        }}).then(r => {{
            const csrf = r.headers.get('x-csrf-token');
            return r.text().then(b => ({{csrf, status: r.status, body: b.substring(0, 200)}}));
        }});
    }}""")
    print(f"  Result: {json.dumps(csrf)}", flush=True)
    
    if csrf.get('csrf'):
        # Step 2: Retry with CSRF
        print(f"\n[2] Login POST WITH CSRF: {csrf['csrf']}...", flush=True)
        login2 = page.evaluate(f"""() => {{
            return fetch('https://auth.roblox.com/v2/login', {{
                method: 'POST',
                credentials: 'include',
                headers: {{
                    'Content-Type': 'application/json',
                    'x-csrf-token': '{csrf['csrf']}',
                }},
                body: JSON.stringify({{
                    ctype: 'Username',
                    cvalue: '{USER}',
                    password: '{PASS}',
                }}),
            }}).then(async r => {{
                const body = await r.text();
                const headers = {{}};
                r.headers.forEach((v, k) => {{ headers[k.toLowerCase()] = v; }});
                return {{
                    status: r.status,
                    headers: headers,
                    body: body.substring(0, 500),
                }};
            }});
        }}""")
        print(f"  Status: {login2.get('status')}", flush=True)
        print(f"  Body: {login2.get('body', '')[:300]}", flush=True)
        
        # Check challenge headers
        for k, v in login2.get('headers', {}).items():
            if 'chall' in k or 'chall' in v.lower() or 'captcha' in k or 'px' in k:
                print(f"  Challenge header: {k} = {v}", flush=True)
        
        time.sleep(10)
    else:
        print(f"  No CSRF token received", flush=True)
    
    print(f"\n=== Arkose frames ===", flush=True)
    for i, f in enumerate(page.frames):
        url = f.url
        if any(x in url for x in ['arkoselabs', 'enforcement', 'game-core', 'api.js']):
            print(f"  [{i}] {url[:200]}", flush=True)
    
    time.sleep(5)
    browser.close()
