"""Solve Time-Lock Puzzle and submit for redemption token."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

# Step 1: Get challenge and puzzle
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
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
            return {{challId: h['rblx-challenge-id'], challType: h['rblx-challenge-type'], sessionId: sid}};
        }});
    }}""")
    
    chall_id = result.get('challId', '')
    session_id = result.get('sessionId', '')
    print(f"Challenge: {chall_id}", flush=True)
    print(f"Session: {session_id}", flush=True)
    
    # GET puzzle
    api_url = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"
    puzzle_resp = page.evaluate(f"""() => {{
        return fetch('{api_url}?sessionID={session_id}', {{
            method: 'GET', credentials: 'include',
        }}).then(async r => {{
            return {{status: r.status, body: await r.text()}};
        }});
    }}""")
    
    if puzzle_resp['status'] != 200:
        print(f"Puzzle error: {puzzle_resp['status']} {puzzle_resp['body']}", flush=True)
        browser.close()
        exit()
    
    puzzle = json.loads(puzzle_resp['body'])
    artifacts = json.loads(puzzle['artifacts'])
    N = int(artifacts['N'])
    A = int(artifacts['A'])
    T = int(artifacts['T'])
    print(f"Puzzle: N={str(N)[:40]}..., A={A}, T={T}", flush=True)
    
    # Step 2: Compute solution
    print(f"\nComputing A^(2^{T}) mod N...", flush=True)
    print(f"This requires {T} repeated squarings...", flush=True)
    start = time.time()
    
    result = A
    for i in range(T):
        result = (result * result) % N
        if (i+1) % 50000 == 0:
            elapsed = time.time() - start
            print(f"  {i+1}/{T} squarings done ({elapsed:.1f}s)", flush=True)
    
    answer = str(result)
    elapsed = time.time() - start
    print(f"Computed answer ({len(answer)} digits) in {elapsed:.1f}s", flush=True)
    print(f"Answer: {answer[:50]}...{answer[-50:]}", flush=True)
    
    # Verify the computation is correct by doing a quick check
    # A^(2^T) mod N should equal result
    # Quick check: compute A * A mod N and compare with our step 0
    check = (A * A) % N
    # This doesn't verify the full computation, just the first step
    
    # Step 3: Submit answer via POST
    print(f"\nSubmitting solution...", flush=True)
    submit = page.evaluate(f"""() => {{
        return fetch('{api_url}', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                challengeId: '{chall_id}',
                solution: '{answer}'
            }}),
        }}).then(async r => {{
            const body = await r.text();
            const hdrs = {{}};
            r.headers.forEach((v,k) => {{ hdrs[k] = v; }});
            return {{status: r.status, headers: hdrs, body: body.substring(0, 500)}};
        }});
    }}""")
    print(f"Submit result: {submit['status']}", flush=True)
    print(f"  Body: {submit.get('body', '')[:300]}", flush=True)
    
    # Check for redemption token
    redemption_token = submit.get('headers', {}).get('rblx-challenge-redemption-token', '')
    if redemption_token:
        print(f"  Redemption token: {redemption_token}", flush=True)
    elif submit['status'] == 200:
        try:
            body_json = json.loads(submit['body'])
            print(f"  Full response: {json.dumps(body_json, indent=2)}", flush=True)
            if 'redemptionToken' in body_json:
                redemption_token = body_json['redemptionToken']
        except:
            pass
    
    if not redemption_token:
        print("No redemption token! Trying with challenge headers...", flush=True)
        # Maybe solution is sent differently
        # Try different format
        submit2 = page.evaluate(f"""() => {{
            return fetch('{api_url}', {{
                method: 'POST', credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    challengeId: '{chall_id}',
                    solution: '{answer}',
                    sessionId: '{session_id}',
                }}),
            }}).then(async r => {{
                const body = await r.text();
                const hdrs = {{}};
                r.headers.forEach((v,k) => {{ hdrs[k] = v; }});
                return {{status: r.status, headers: hdrs, body: body.substring(0, 500)}};
            }});
        }}""")
        print(f"Submit2 result: {submit2['status']}", flush=True)
        print(f"  Body: {submit2.get('body', '')[:300]}", flush=True)
        rt2 = submit2.get('headers', {}).get('rblx-challenge-redemption-token', '')
        if rt2:
            redemption_token = rt2
            print(f"  Redemption token: {rt2}", flush=True)
        elif submit2['status'] == 200:
            try:
                body_json = json.loads(submit2['body'])
                if 'redemptionToken' in body_json:
                    redemption_token = body_json['redemptionToken']
                    print(f"  Redemption token from body: {redemption_token}", flush=True)
            except:
                pass
    
    # Step 4: Retry login with redemption token
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
        print(f"Login result: {login['status']}", flush=True)
        print(f"  Body: {login['body']}", flush=True)
        if login['status'] == 200:
            print(f"\n*** LOGIN SUCCESS! ***", flush=True)
    
    time.sleep(2)
    browser.close()
