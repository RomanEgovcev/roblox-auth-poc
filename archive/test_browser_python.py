"""Full flow: browser for initial state, Python for login retry."""
import os, time, json, base64, http.cookiejar

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
    time.sleep(3)
    
    # 1. Get CSRF
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    
    # 2. Get challenge
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
            return {{challId: h['rblx-challenge-id'], sessionId: sid, meta: meta}};
        }});
    }}""")
    chall_id = chall['challId']
    session_id = chall['sessionId']
    meta_raw = chall['meta']
    
    # Show full metadata
    if meta_raw:
        meta = json.loads(base64.b64decode(meta_raw))
        print(f"Challenge: {chall_id}", flush=True)
        print(f"Session: {session_id}", flush=True)
        print(f"Meta: {json.dumps(meta, indent=2)}", flush=True)
    else:
        print("No metadata!", flush=True)
        browser.close()
        exit()
    
    # 3. Solve puzzle
    api_url = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"
    puzzle_resp = page.evaluate(f"""async () => {{
        const r = await fetch('{api_url}?sessionID={session_id}', {{method: 'GET', credentials: 'include'}});
        return {{status: r.status, body: await r.text()}};
    }}""")
    puzzle = json.loads(puzzle_resp['body'])
    artifacts = json.loads(puzzle['artifacts'])
    N, A, T = int(artifacts['N']), int(artifacts['A']), int(artifacts['T'])
    print(f"Puzzle: T={T}, A={A}", flush=True)
    
    print(f"Computing...", flush=True)
    start = time.time()
    result = A
    for i in range(T):
        result = (result * result) % N
    answer = str(result)
    print(f"Answer ({len(answer)} digits) in {time.time()-start:.1f}s", flush=True)
    
    # 4. Submit solution
    submit = page.evaluate(f"""async () => {{
        const r = await fetch('{api_url}', {{method: 'POST', credentials: 'include', headers: {{'Content-Type': 'application/json'}}, body: '{{}}'}});
        const csrf2 = r.headers.get('x-csrf-token');
        const r2 = await fetch('{api_url}', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': csrf2}},
            body: JSON.stringify({{solution: '{answer}', sessionId: '{session_id}'}})
        }});
        return {{status: r2.status, body: await r2.text(), csrf: csrf2}};
    }}""")
    if submit['status'] != 200:
        print(f"Submit failed: {submit}", flush=True)
        browser.close()
        exit()
    
    data = json.loads(submit['body'])
    redemption_token = data['redemptionToken']
    print(f"Redemption token: {redemption_token}", flush=True)
    print(f"API CSRF: {submit['csrf']}", flush=True)
    
    # 5. Export cookies to Python session
    cookies = context.cookies()
    print(f"\nCookies ({len(cookies)}):", flush=True)
    for c in cookies:
        print(f"  {c['name']}: {c['value'][:50]}...", flush=True)
    
    browser.close()
    
# 6. Use Python httpx to make login request with redemption token
print(f"\n--- Making login request from Python ---", flush=True)

import httpx

# Build cookie dict
cookie_dict = {}
for c in cookies:
    cookie_dict[c['name']] = c['value']

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Content-Type': 'application/json',
    'Origin': 'https://www.roblox.com',
    'Referer': 'https://www.roblox.com/login',
}

with httpx.Client(headers=headers, cookies=cookie_dict) as client:
    # First get CSRF
    r = client.post('https://auth.roblox.com/v2/login', json={'ctype': 'Username', 'cvalue': USER, 'password': PASS})
    csrf_final = r.headers.get('x-csrf-token', '')
    print(f"Python CSRF: {csrf_final}", flush=True)
    
    # Now retry with redemption token
    r2 = client.post('https://auth.roblox.com/v2/login', 
        json={'ctype': 'Username', 'cvalue': USER, 'password': PASS},
        headers={
            'x-csrf-token': csrf_final,
            'rblx-challenge-id': chall_id,
            'rblx-challenge-type': 'proofofwork',
            'rblx-challenge-redemption-token': redemption_token,
        }
    )
    print(f"Python login: {r2.status_code}", flush=True)
    print(f"  Body: {r2.text[:300]}", flush=True)
    print(f"  Headers: {dict(r2.headers)}", flush=True)
