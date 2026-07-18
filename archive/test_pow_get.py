"""GET pow-puzzle with sessionID parameter (as in JS code)."""
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
    
    # Get CSRF and challenge with sessionId from metadata
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    
    # Get full metadata
    result = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(async r => {{
            const h = {{}};
            r.headers.forEach((v,k) => {{ h[k] = v; }});
            const meta = h['rblx-challenge-metadata'] || '';
            let sessionId = '';
            try {{ sessionId = JSON.parse(atob(meta)).sessionId; }} catch(e) {{}}
            return {{
                id: h['rblx-challenge-id'],
                type: h['rblx-challenge-type'],
                sessionId: sessionId,
                metaB64: meta,
            }};
        }});
    }}""")
    
    chall_id = result.get('id', '')
    session_id = result.get('sessionId', '')
    print(f"Challenge: {chall_id}", flush=True)
    print(f"Session: {session_id}", flush=True)
    
    if not chall_id or not session_id:
        print("Missing challenge data!", flush=True)
        browser.close()
        exit()
    
    api_url = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"
    
    # GET with sessionID (as in JS: nO = httpService.get(n_, {sessionID: t}))
    print(f"\n[GET] with sessionID...", flush=True)
    resp = page.evaluate(f"""() => {{
        return fetch('{api_url}?sessionID={session_id}', {{
            method: 'GET', credentials: 'include',
        }}).then(async r => {{
            const body = await r.text();
            const hdrs = {{}};
            r.headers.forEach((v,k) => {{ hdrs[k] = v; }});
            return {{status: r.status, headers: hdrs, body: body.substring(0, 2000)}};
        }});
    }}""")
    print(f"  Status: {resp['status']}", flush=True)
    print(f"  Body: {resp['body']}", flush=True)
    
    if resp['status'] == 200:
        try:
            puzzle = json.loads(resp['body'])
            print(f"\nPuzzle data: {json.dumps(puzzle, indent=2)}", flush=True)
        except:
            pass
    
    # If GET fails, try GET with sessionId (lowercase d)
    if resp['status'] != 200:
        print(f"\n[GET] with sessionId (lowercase)...", flush=True)
        resp2 = page.evaluate(f"""() => {{
            return fetch('{api_url}?sessionId={session_id}', {{
                method: 'GET', credentials: 'include',
            }}).then(async r => {{
                const body = await r.text();
                return {{status: r.status, body: body.substring(0, 1000)}};
            }});
        }}""")
        print(f"  Status: {resp2['status']}", flush=True)
        print(f"  Body: {resp2['body']}", flush=True)
    
    time.sleep(2)
    browser.close()
