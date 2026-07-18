"""Try login retry without CSRF precheck - use original CSRF."""
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
    time.sleep(3)
    
    # 1. Get CSRF + challenge in fastest possible sequence
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    
    chall = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(async r => {{
            const h = {{}};
            r.headers.forEach((v,k) => {{ h[k] = v; }});
            const meta = h['rblx-challenge-metadata'] || '';
            let sid = '';
            try {{ sid = JSON.parse(atob(meta)).sessionId; }} catch(e) {{}}
            return {{challId: h['rblx-challenge-id'], sessionId: sid}};
        }});
    }}""")
    chall_id = chall['challId']
    session_id = chall['sessionId']
    print(f"CSRF: {csrf}", flush=True)
    print(f"Challenge: {chall_id}", flush=True)
    print(f"Session: {session_id}", flush=True)
    
    # 2. Get puzzle and compute solution
    api_url = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"
    puzzle_resp = page.evaluate(f"""async () => {{
        const r = await fetch('{api_url}?sessionID={session_id}', {{method: 'GET', credentials: 'include'}});
        return {{status: r.status, body: await r.text()}};
    }}""")
    puzzle = json.loads(puzzle_resp['body'])
    artifacts = json.loads(puzzle['artifacts'])
    N, A, T = int(artifacts['N']), int(artifacts['A']), int(artifacts['T'])
    print(f"Puzzle: T={T}", flush=True)
    
    print(f"Computing...", flush=True)
    start = time.time()
    result = A
    for i in range(T):
        result = (result * result) % N
    answer = str(result)
    print(f"Answer ({len(answer)} digits) in {time.time()-start:.1f}s", flush=True)
    
    # 3. Submit solution & get redemption token
    submit = page.evaluate(f"""async () => {{
        const r = await fetch('{api_url}', {{method: 'POST', credentials: 'include', headers: {{'Content-Type': 'application/json'}}, body: '{{}}'}});
        const csrf2 = r.headers.get('x-csrf-token');
        const r2 = await fetch('{api_url}', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': csrf2}},
            body: JSON.stringify({{solution: '{answer}', sessionId: '{session_id}'}})
        }});
        const body = await r2.text();
        const hdrs = {{}};
        r2.headers.forEach((v,k) => {{ hdrs[k] = v; }});
        return {{status: r2.status, body: body, headers: hdrs, csrf: csrf2}};
    }}""")
    
    if submit['status'] != 200:
        print(f"Submit failed: {submit}", flush=True)
        browser.close()
        exit()
    
    data = json.loads(submit['body'])
    redemption_token = data['redemptionToken']
    apis_csrf = submit['csrf']
    print(f"Redemption token: {redemption_token}", flush=True)
    print(f"APIs CSRF: {apis_csrf}", flush=True)
    
    # 4. Retry login - use the ORIGINAL CSRF, not a fresh one
    # Add redemption headers via page.route to avoid PX
    login_result = [None]
    
    def handle_login(route):
        req = route.request
        if req.method == 'POST' and '/v2/login' in req.url:
            h = dict(req.headers)
            h['rblx-challenge-id'] = chall_id
            h['rblx-challenge-type'] = 'proofofwork'
            h['rblx-challenge-redemption-token'] = redemption_token
            route.continue_(headers=h)
        else:
            route.continue_()
    
    page.route("**/v2/login", handle_login)
    
    # Use original CSRF, no precheck
    login_resp = page.evaluate(f"""async () => {{
        const r = await fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}})
        }});
        const hdrs = {{}};
        r.headers.forEach((v,k) => {{ hdrs[k] = v; }});
        return {{status: r.status, headers: hdrs, body: await r.text()}};
    }}""")
    
    print(f"\nLogin (original CSRF): {login_resp['status']}", flush=True)
    print(f"  Body: {login_resp.get('body', '')[:300]}", flush=True)
    
    # Check headers for clues
    for k, v in login_resp.get('headers', {}).items():
        if 'chall' in k.lower() or 'token' in k.lower() or 'csrf' in k.lower():
            print(f"  {k}: {v}", flush=True)
    
    if login_resp['status'] == 200:
        print("\n*** LOGIN SUCCESS! ***", flush=True)
    else:
        new_chall = login_resp.get('headers', {}).get('rblx-challenge-id', '')
        if new_chall:
            print(f"  New challenge: {new_chall}", flush=True)
    
    time.sleep(3)
    print(f"Final URL: {page.url}", flush=True)
    browser.close()
