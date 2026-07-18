"""Clean approach: capture challenge, then add solution headers via route."""
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
    
    # Step 2: Get challenge via route interception
    challenge_info = {}
    
    def capture(route):
        if route.request.method == 'POST' and '/v2/login' in route.request.url:
            resp = page.request.fetch(route.request)
            headers = dict(resp.headers)
            cid = headers.get('rblx-challenge-id', '')
            if cid:
                challenge_info['id'] = cid
                challenge_info['type'] = headers.get('rblx-challenge-type', '')
                challenge_info['meta_b64'] = headers.get('rblx-challenge-metadata', '')
                print(f"Challenge: {cid} ({challenge_info['type']})", flush=True)
            route.fulfill(status=resp.status, headers=headers, body=resp.body())
        else:
            route.continue_()
    
    page.route("https://auth.roblox.com/v2/login", capture)
    
    page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }});
    }}""")
    time.sleep(2)
    
    page.unroute("https://auth.roblox.com/v2/login", capture)
    
    if not challenge_info.get('id'):
        print("No challenge!", flush=True)
        browser.close()
        exit()
    
    chall_id = challenge_info['id']
    chall_type = challenge_info['type']
    
    # Step 3: Get fresh CSRF
    csrf2 = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF2: {csrf2}", flush=True)
    
    # Step 4: Route next login POST to add challenge solution
    solution_result = [None]
    
    def solve(route):
        if route.request.method == 'POST' and '/v2/login' in route.request.url:
            # Get original headers and add challenge solution
            orig_headers = route.request.headers
            orig_headers['rblx-challenge-id'] = chall_id
            orig_headers['rblx-challenge-type'] = chall_type
            orig_headers['rblx-challenge-solution'] = '0'
            
            # Continue with modified headers
            route.continue_(headers=orig_headers)
        else:
            route.continue_()
    
    page.route("https://auth.roblox.com/v2/login", solve)
    
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
    print(f"\nLogin result: {result.get('status')}", flush=True)
    print(f"  Body: {result.get('body', '')[:200]}", flush=True)
    
    time.sleep(2)
    browser.close()
