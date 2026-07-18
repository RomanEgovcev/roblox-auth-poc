"""Use page.route to add redemption token headers at CDP level."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"
REDEMPTION_TOKEN = ""  # Will be set after solving

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # 1. Get auth CSRF and challenge
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
    print(f"Puzzle: N={str(N)[:20]}..., A={A}, T={T}", flush=True)
    
    print(f"Computing...", flush=True)
    start = time.time()
    result = A
    for i in range(T):
        result = (result * result) % N
    answer = str(result)
    print(f"Answer ({len(answer)} digits) in {time.time()-start:.1f}s", flush=True)
    
    # 3. Submit solution
    csrf_api = page.evaluate(f"""async () => {{
        const r = await fetch('{api_url}', {{method: 'POST', credentials: 'include', headers: {{'Content-Type': 'application/json'}}, body: '{{}}'}});
        return r.headers.get('x-csrf-token');
    }}""")
    
    submit = page.evaluate(f"""async () => {{
        const r = await fetch('{api_url}', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf_api}'}},
            body: JSON.stringify({{solution: '{answer}', sessionId: '{session_id}'}})
        }});
        return {{status: r.status, body: await r.text()}};
    }}""")
    print(f"Submit: {submit['status']} - {submit['body'][:100]}", flush=True)
    
    redemption_token = ''
    if submit['status'] == 200:
        data = json.loads(submit['body'])
        redemption_token = data.get('redemptionToken', '')
        print(f"Redemption token: {redemption_token}", flush=True)
    
    if not redemption_token:
        print("No redemption token!", flush=True)
        browser.close()
        exit()
    
    # 4. Retry login - use page.route to add headers at CDP level
    print(f"\nRetrying login via route interception...", flush=True)
    
    def handle_login(route):
        if route.request.method == 'POST' and '/v2/login' in route.request.url:
            h = dict(route.request.headers)
            # Only add redemption for requests with x-csrf-token (actual login, not CSRF prechecks)
            if 'x-csrf-token' in h:
                h['rblx-challenge-id'] = chall_id
                h['rblx-challenge-type'] = 'proofofwork'
                h['rblx-challenge-redemption-token'] = redemption_token
            route.continue_(headers=h)
        else:
            route.continue_()
    
    page.route("https://auth.roblox.com/v2/login", handle_login)
    
    # Make login request (route handler will add headers)
    login_resp = page.evaluate(f"""async () => {{
        // First get fresh CSRF
        const csrfResp = await fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}})
        }});
        const csrf3 = csrfResp.headers.get('x-csrf-token');
        
        // Now login with CSRF (route handler adds redemption headers)
        const r = await fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': csrf3}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}})
        }});
        const hdrs = {{}};
        r.headers.forEach((v,k) => {{ hdrs[k] = v; }});
        return {{status: r.status, headers: hdrs, body: await r.text()}};
    }}""")
    
    print(f"Login: {login_resp['status']}", flush=True)
    print(f"  Body: {login_resp.get('body', '')[:300]}", flush=True)
    
    if login_resp['status'] == 200:
        print("\n*** LOGIN SUCCESS! ***", flush=True)
    else:
        new_chall = login_resp.get('headers', {}).get('rblx-challenge-id', '')
        if new_chall:
            print(f"  New challenge: {new_chall}", flush=True)
    
    time.sleep(5)
    print(f"Final URL: {page.url}", flush=True)
    browser.close()
