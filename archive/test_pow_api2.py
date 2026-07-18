"""POST to pow-puzzle with CSRF token."""
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
    
    # Get CSRF and challenge
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
            return {{id: h['rblx-challenge-id'], type: h['rblx-challenge-type'], meta: meta,
                     sessionId: meta ? JSON.parse(atob(meta)).sessionId : ''}};
        }});
    }}""")
    
    chall_id = chall.get('id', '')
    session_id = chall.get('sessionId', '')
    print(f"Challenge: {chall_id}", flush=True)
    print(f"Session: {session_id}", flush=True)
    
    if not chall_id:
        print("No challenge!", flush=True)
        browser.close()
        exit()
    
    api_url = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"
    
    # First get CSRF for apis.roblox.com
    csrf_apis = page.evaluate(f"""() => {{
        return fetch('{api_url}', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{}}),
        }}).then(async r => {{
            const csrf = r.headers.get('x-csrf-token');
            const body = await r.text();
            return {{csrf, status: r.status, body: body.substring(0, 200)}};
        }});
    }}""")
    print(f"\nCSRF for apis: {csrf_apis}", flush=True)
    
    # POST with CSRF and challengeId
    if csrf_apis.get('csrf'):
        result = page.evaluate(f"""() => {{
            return fetch('{api_url}', {{
                method: 'POST', credentials: 'include',
                headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf_apis['csrf']}'}},
                body: JSON.stringify({{challengeId: '{chall_id}'}}),
            }}).then(async r => {{
                const body = await r.text();
                return {{status: r.status, body: body.substring(0, 1000)}};
            }});
        }}""")
        print(f"\nPOST with CSRF:", flush=True)
        print(f"  Status: {result['status']}", flush=True)
        print(f"  Body: {result['body']}", flush=True)
    
    # Also try with sessionId as parameter
    result2 = page.evaluate(f"""() => {{
        return fetch('{api_url}', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf_apis.get('csrf', '')}'}},
            body: JSON.stringify({{sessionId: '{session_id}'}}),
        }}).then(async r => {{
            const body = await r.text();
            return {{status: r.status, body: body.substring(0, 1000)}};
        }});
    }}""")
    print(f"\nPOST with sessionId:", flush=True)
    print(f"  Status: {result2['status']}", flush=True)
    print(f"  Body: {result2['body']}", flush=True)
    
    time.sleep(2)
    browser.close()
