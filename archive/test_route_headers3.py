"""Use page.on('response') to capture, then page.route to add headers."""
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
    
    # Capture challenge from response (non-blocking)
    challenge_info = {}
    page.on("response", lambda r: challenge_info.update({
        "id": r.headers.get('rblx-challenge-id', ''),
        "type": r.headers.get('rblx-challenge-type', ''),
        "meta": r.headers.get('rblx-challenge-metadata', ''),
    }) if '/v2/login' in r.url and r.headers.get('rblx-challenge-id') else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Get CSRF
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF: {csrf}", flush=True)
    
    # Trigger login to get challenge
    page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }});
    }}""")
    time.sleep(2)
    
    chall_id = challenge_info.get('id', '')
    chall_type = challenge_info.get('type', '')
    print(f"Challenge: {chall_id} ({chall_type})", flush=True)
    
    if not chall_id:
        print("No challenge!", flush=True)
        browser.close()
        exit()
    
    # Get fresh CSRF (no challenge headers needed for this one)
    csrf2 = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF2: {csrf2}", flush=True)
    
    # Route login POSTs to add challenge solution headers
    # Only add to requests that have x-csrf-token (actual login attempts, not CSRF prechecks)
    def solve(route):
        if route.request.method == 'POST' and '/v2/login' in route.request.url:
            h = dict(route.request.headers)
            if 'x-csrf-token' in h:
                h['rblx-challenge-id'] = chall_id
                h['rblx-challenge-type'] = chall_type
                h['rblx-challenge-solution'] = '0'
            route.continue_(headers=h)
        else:
            route.continue_()
    
    page.route("https://auth.roblox.com/v2/login", solve)
    
    # Make login request with solution
    result = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf2}'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(async r => {{
            const body = await r.text();
            const hdrs = {{}};
            r.headers.forEach((v, k) => {{ hdrs[k] = v; }});
            return {{status: r.status, headers: hdrs, body: body.substring(0, 300)}};
        }});
    }}""")
    print(f"\nLogin result: {result.get('status')}", flush=True)
    print(f"  Body: {result.get('body', '')[:200]}", flush=True)
    new_chall = result.get('headers', {}).get('rblx-challenge-id', '')
    if new_chall:
        print(f"  New challenge: {new_chall} ({result.get('headers', {}).get('rblx-challenge-type', '')})", flush=True)
    
    time.sleep(2)
    browser.close()
