"""Full login flow: challenge -> puzzle -> solve -> redeem -> login."""
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
    
    # 1. Get auth CSRF
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"Auth CSRF: {csrf}", flush=True)
    
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
            return {{challId: h['rblx-challenge-id'], sessionId: sid}};
        }});
    }}""")
    chall_id = chall['challId']
    session_id = chall['sessionId']
    print(f"Challenge: {chall_id}", flush=True)
    print(f"Session: {session_id}", flush=True)
    
    # 3. Get puzzle
    api_url = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"
    puzzle_resp = page.evaluate(f"""async () => {{
        const r = await fetch('{api_url}?sessionID={session_id}', {{method: 'GET', credentials: 'include'}});
        return {{status: r.status, body: await r.text()}};
    }}""")
    puzzle = json.loads(puzzle_resp['body'])
    artifacts = json.loads(puzzle['artifacts'])
    N, A, T = int(artifacts['N']), int(artifacts['A']), int(artifacts['T'])
    print(f"Puzzle: N={str(N)[:20]}..., A={A}, T={T}", flush=True)
    
    # 4. Compute solution (Python)
    print(f"Computing A^(2^{T}) mod N...", flush=True)
    start = time.time()
    result = A
    for i in range(T):
        result = (result * result) % N
    answer = str(result)
    print(f"Answer ({len(answer)} digits) in {time.time()-start:.1f}s", flush=True)
    
    # 5. Get CSRF for apis
    csrf_api = page.evaluate(f"""async () => {{
        const r = await fetch('{api_url}', {{method: 'POST', credentials: 'include', headers: {{'Content-Type': 'application/json'}}, body: '{{}}'}});
        return r.headers.get('x-csrf-token');
    }}""")
    print(f"API CSRF: {csrf_api}", flush=True)
    
    # 6. Submit solution
    submit = page.evaluate(f"""async () => {{
        const r = await fetch('{api_url}', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf_api}'}},
            body: JSON.stringify({{solution: '{answer}', sessionId: '{session_id}'}})
        }});
        const hdrs = {{}};
        r.headers.forEach((v,k) => {{ hdrs[k] = v; }});
        return {{status: r.status, headers: hdrs, body: await r.text()}};
    }}""")
    print(f"Submit: {submit['status']}", flush=True)
    print(f"  Body: {submit['body']}", flush=True)
    
    redemption_token = ''
    if submit['status'] == 200:
        data = json.loads(submit['body'])
        redemption_token = data.get('redemptionToken', '')
        print(f"  Redemption token: {redemption_token}", flush=True)
    
    if not redemption_token:
        print("No redemption token!", flush=True)
        browser.close()
        exit()
    
    # 7. Retry login with redemption token
    print(f"\nRetrying login with redemption token...", flush=True)
    csrf3 = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}})
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    
    login = page.evaluate(f"""async () => {{
        const r = await fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{
                'Content-Type': 'application/json',
                'x-csrf-token': '{csrf3}',
                'rblx-challenge-id': '{chall_id}',
                'rblx-challenge-type': 'proofofwork',
                'rblx-challenge-redemption-token': '{redemption_token}',
            }},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}})
        }});
        const hdrs = {{}};
        r.headers.forEach((v,k) => {{ hdrs[k] = v; }});
        return {{status: r.status, headers: hdrs, body: await r.text()}};
    }}""")
    print(f"Login: {login['status']}", flush=True)
    print(f"  Body: {login.get('body', '')[:300]}", flush=True)
    
    if login['status'] == 200:
        print("\n*** LOGIN SUCCESS! ***", flush=True)
    else:
        new_chall = login.get('headers', {}).get('rblx-challenge-id', '')
        if new_chall:
            print(f"  New challenge: {new_chall}", flush=True)
    
    time.sleep(5)
    print(f"Final URL: {page.url}", flush=True)
    browser.close()
