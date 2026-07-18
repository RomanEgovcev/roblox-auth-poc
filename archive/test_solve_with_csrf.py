"""Get CSRF for apis.roblox.com, then submit puzzle solution."""
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
    
    # Step 1: Get auth CSRF and challenge
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    
    result = page.evaluate(f"""() => {{
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
    
    chall_id = result['challId']
    session_id = result['sessionId']
    print(f"Challenge: {chall_id}", flush=True)
    print(f"Session: {session_id}", flush=True)
    
    api_url = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"
    
    # Step 2: Get puzzle
    puzzle_resp = page.evaluate(f"""() => {{
        return fetch('{api_url}?sessionID={session_id}', {{
            method: 'GET', credentials: 'include',
        }}).then(async r => {{ return {{status: r.status, body: await r.text()}}; }});
    }}""")
    
    puzzle = json.loads(puzzle_resp['body'])
    artifacts = json.loads(puzzle['artifacts'])
    N, A, T = int(artifacts['N']), int(artifacts['A']), int(artifacts['T'])
    print(f"Puzzle: N={str(N)[:30]}..., A={A}, T={T}", flush=True)
    
    # Step 3: Get CSRF for apis.roblox.com
    # Send a POST that will fail to get CSRF
    csrf_resp = page.evaluate(f"""() => {{
        return fetch('{api_url}', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{}}),
        }}).then(async r => {{
            const csrf = r.headers.get('x-csrf-token');
            return {{status: r.status, csrf: csrf, body: await r.text()}};
        }});
    }}""")
    csrf_api = csrf_resp.get('csrf', '')
    print(f"CSRF (apis): {csrf_api}", flush=True)
    
    if not csrf_api:
        # Try getting CSRF from a different endpoint
        print("No CSRF, trying alternative method...", flush=True)
        csrf_api = page.evaluate(f"""() => {{
            return fetch('{api_url}/dummy', {{
                method: 'POST', credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{}}),
            }}).then(r => r.headers.get('x-csrf-token'));
        }}""")
        print(f"CSRF (apis, alt): {csrf_api}", flush=True)
    
    if not csrf_api:
        print("Cannot get CSRF for apis.roblox.com!", flush=True)
        browser.close()
        exit()
    
    # Step 4: Compute solution
    print(f"\nComputing A^(2^{T}) mod N ({T} squarings)...", flush=True)
    start = time.time()
    result_val = A
    for i in range(T):
        result_val = (result_val * result_val) % N
    answer = str(result_val)
    elapsed = time.time() - start
    print(f"Answer computed ({len(answer)} digits) in {elapsed:.1f}s", flush=True)
    
    # Step 5: Submit with CSRF
    print(f"\nSubmitting solution with CSRF...", flush=True)
    submit = page.evaluate(f"""() => {{
        return fetch('{api_url}', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf_api}'}},
            body: JSON.stringify({{challengeId: '{chall_id}', solution: '{answer}'}}),
        }}).then(async r => {{
            const hdrs = {{}};
            r.headers.forEach((v,k) => {{ hdrs[k] = v; }});
            return {{status: r.status, headers: hdrs, body: await r.text()}};
        }});
    }}""")
    print(f"Submit: {submit['status']}", flush=True)
    print(f"  Body: {submit.get('body', '')[:300]}", flush=True)
    
    redemption_token = submit.get('headers', {}).get('rblx-challenge-redemption-token', '')
    if not redemption_token and submit['status'] == 200:
        try:
            data = json.loads(submit['body'])
            redemption_token = data.get('redemptionToken', data.get('redemption_token', ''))
            print(f"  Redemption token from body: {redemption_token}", flush=True)
        except:
            pass
    
    if not redemption_token:
        print("Still no redemption token!", flush=True)
        print(f"  All headers: {json.dumps(dict(submit.get('headers', {})), indent=2)}", flush=True)
    
    # Step 6: Submit solution and verification in one flow
    # The JS code calls verifyPuzzle which might have different format
    # nk = function(t, n) where t is challengeId and n is solution
    # The body sent: {challengeId: t, solution: n}
    # But maybe the solution needs to be in a different format?
    
    # Try without challengeId
    if not redemption_token:
        submit2 = page.evaluate(f"""() => {{
            return fetch('{api_url}', {{
                method: 'POST', credentials: 'include',
                headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf_api}'}},
                body: JSON.stringify({{solution: '{answer}', sessionId: '{session_id}'}}),
            }}).then(async r => {{
                return {{status: r.status, body: await r.text()}};
            }});
        }}""")
        print(f"Submit2 (no challId): {submit2['status']}", flush=True)
        print(f"  Body: {submit2.get('body', '')[:300]}", flush=True)
    
    # Step 7: If we have redemption token, try login
    if redemption_token:
        print(f"\nRetrying login with redemption token...", flush=True)
        csrf3 = page.evaluate(f"""() => {{
            return fetch('https://auth.roblox.com/v2/login', {{
                method: 'POST', credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
            }}).then(r => r.headers.get('x-csrf-token'));
        }}""")
        
        login = page.evaluate(f"""() => {{
            return fetch('https://auth.roblox.com/v2/login', {{
                method: 'POST', credentials: 'include',
                headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf3}',
                    'rblx-challenge-id': '{chall_id}',
                    'rblx-challenge-type': 'proofofwork',
                    'rblx-challenge-redemption-token': '{redemption_token}',
                }},
                body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
            }}).then(async r => {{
                const body = await r.text();
                return {{status: r.status, body: body.substring(0, 300)}};
            }});
        }}""")
        print(f"Login: {login['status']}", flush=True)
        print(f"  Body: {login['body']}", flush=True)
        if login['status'] == 200:
            print("\n*** LOGIN SUCCESS! ***", flush=True)
    else:
        print("\nNo redemption token obtained - login cannot proceed", flush=True)
    
    time.sleep(2)
    browser.close()
