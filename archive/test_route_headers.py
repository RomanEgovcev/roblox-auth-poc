"""Use page.route to add challenge solution headers at CDP level (bypasses PX JS intercept)."""
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
    
    # Step 1: Get CSRF
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF: {csrf}", flush=True)
    
    # Step 2: Get challenge
    chall_id_holder = ['']
    
    def capture_challenge(route):
        if route.request.method == 'POST' and '/v2/login' in route.request.url:
            resp = page.request.fetch(route.request)
            headers = dict(resp.headers)
            cid = headers.get('rblx-challenge-id', '')
            if cid:
                chall_id_holder[0] = cid
                print(f"\nCaptured challenge: {cid}", flush=True)
            route.fulfill(status=resp.status, headers=headers, body=resp.body())
        else:
            route.continue_()
    
    page.route("https://auth.roblox.com/v2/login", capture_challenge)
    
    # Make initial login POST via page evaluate
    page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }});
    }}""")
    time.sleep(2)
    
    if not chall_id_holder[0]:
        print("No challenge captured!", flush=True)
        browser.close()
        exit()
    
    chall_id = chall_id_holder[0]
    
    # Step 3: Now set up route to ADD challenge solution headers
    # We'll intercept the next login POST and add challenge headers
    chall_solved = [False]
    
    def add_challenge_headers(route):
        if route.request.method == 'POST' and '/v2/login' in route.request.url:
            # Get fresh CSRF first
            h = route.request.headers
            # Add challenge headers
            h['rblx-challenge-id'] = chall_id
            h['rblx-challenge-type'] = 'proofofwork'
            h['rblx-challenge-solution'] = '0'  # Try "0" as solution
            route.continue_(headers=h)
        else:
            route.continue_()
    
    page.route("https://auth.roblox.com/v2/login", add_challenge_headers)
    
    # Get fresh CSRF (using uncaptured fetch)
    page.remove_route("https://auth.roblox.com/v2/login", capture_challenge)
    
    csrf2 = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF2: {csrf2}", flush=True)
    
    # Now make login POST - route should add challenge headers
    result = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf2}'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(async r => {{
            const body = await r.text();
            return {{status: r.status, body: body.substring(0, 300)}};
        }});
    }}""")
    print(f"\nLogin with challenge: {result.get('status', 'FAIL')}", flush=True)
    print(f"  Body: {result.get('body', '')}", flush=True)
    
    time.sleep(2)
    browser.close()
