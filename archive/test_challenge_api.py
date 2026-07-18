"""Solve challenge and get redemption token."""
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
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[40:120]}" if any(x in r.url for x in ['auth', 'challenge', 'collector']) else "", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Get CSRF
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF: {csrf}", flush=True)
    
    if not csrf:
        print("No CSRF token!", flush=True)
        browser.close()
        exit()
    
    # Login with CSRF to get challenge
    chall = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(async r => {{
            const headers = {{}};
            r.headers.forEach((v, k) => {{ headers[k.toLowerCase()] = v; }});
            const body = await r.text();
            return {{status: r.status, headers, body: body.substring(0, 500)}};
        }});
    }}""")
    print(f"\nChallenge response:", flush=True)
    print(f"  Status: {chall['status']}", flush=True)
    
    chall_id = chall.get('headers', {}).get('rblx-challenge-id', '')
    chall_type = chall.get('headers', {}).get('rblx-challenge-type', '')
    chall_meta_b64 = chall.get('headers', {}).get('rblx-challenge-metadata', '')
    
    print(f"  Challenge ID: {chall_id}", flush=True)
    print(f"  Challenge Type: {chall_type}", flush=True)
    
    if chall_meta_b64:
        try:
            decoded = base64.b64decode(chall_meta_b64).decode('utf-8')
            print(f"  Metadata (decoded): {json.dumps(json.loads(decoded), indent=2)}", flush=True)
            meta = json.loads(decoded)
        except:
            print(f"  Metadata (raw): {chall_meta_b64}", flush=True)
            meta = {}
    else:
        meta = {}
    
    if chall_id:
        # Try GET challenge detail
        print(f"\n[GET challenge detail]", flush=True)
        detail = page.evaluate(f"""() => {{
            return fetch('https://auth.roblox.com/v1/challenge/{chall_id}', {{
                method: 'GET', credentials: 'include',
            }}).then(async r => {{
                const body = await r.text();
                return {{status: r.status, body: body.substring(0, 1000)}};
            }});
        }}""")
        print(f"  Status: {detail['status']}", flush=True)
        print(f"  Body: {detail['body'][:300]}", flush=True)
        
        # Try POST challenge solution (empty solution)
        print(f"\n[POST challenge solution]", flush=True)
        solution = page.evaluate(f"""() => {{
            return fetch('https://auth.roblox.com/v1/challenge/{chall_id}', {{
                method: 'POST', credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    challengeId: '{chall_id}',
                    challengeType: '{chall_type}',
                    challengeMetadata: '{chall_meta_b64}',
                    solution: {{}},
                }}),
            }}).then(async r => {{
                const body = await r.text();
                const headers = {{}};
                r.headers.forEach((v, k) => {{ headers[k.toLowerCase()] = v; }});
                return {{status: r.status, headers, body: body.substring(0, 500)}};
            }});
        }}""")
        print(f"  Status: {solution['status']}", flush=True)
        print(f"  Body: {solution['body']}", flush=True)
        
        if solution['status'] == 200 or solution.get('headers', {}).get('rblx-challenge-redemption-token'):
            token = solution.get('headers', {}).get('rblx-challenge-redemption-token', '')
            print(f"\n  Redemption token: {token}", flush=True)
        
    time.sleep(3)
    browser.close()
