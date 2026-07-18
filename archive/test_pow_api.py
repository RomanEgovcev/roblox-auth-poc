"""Call proof-of-work API to get puzzle parameters and solve."""
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
    
    challeng = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(async r => {{
            const hdrs = {{}};
            r.headers.forEach((v,k) => {{ hdrs[k] = v; }});
            return {{id: hdrs['rblx-challenge-id'], type: hdrs['rblx-challenge-type'], meta: hdrs['rblx-challenge-metadata']}};
        }});
    }}""")
    
    chall_id = challeng.get('id', '')
    chall_type = challeng.get('type', '')
    chall_meta_b64 = challeng.get('meta', '')
    print(f"Challenge: {chall_id} ({chall_type})", flush=True)
    
    if not chall_id:
        print("No challenge!", flush=True)
        browser.close()
        exit()
    
    # Try calling POW API using fetch (with cookies from browser)
    api_url = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"
    
    # GET puzzle params
    print(f"\n[GET] {api_url}...", flush=True)
    puzzle_get = page.evaluate(f"""() => {{
        return fetch('{api_url}?challengeId={chall_id}', {{
            method: 'GET', credentials: 'include',
        }}).then(async r => {{
            const body = await r.text();
            return {{status: r.status, body: body.substring(0, 300)}};
        }});
    }}""")
    print(f"  Status: {puzzle_get['status']}", flush=True)
    print(f"  Body: {puzzle_get['body']}", flush=True)
    
    # Try POST to get puzzle (with challengeId)
    print(f"\n[POST] {api_url}...", flush=True)
    puzzle_post = page.evaluate(f"""() => {{
        return fetch('{api_url}', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{challengeId: '{chall_id}'}}),
        }}).then(async r => {{
            const body = await r.text();
            const hdrs = {{}};
            r.headers.forEach((v,k) => {{ hdrs[k] = v; }});
            return {{status: r.status, headers: hdrs, body: body.substring(0, 1000)}};
        }});
    }}""")
    print(f"  Status: {puzzle_post['status']}", flush=True)
    print(f"  Body: {puzzle_post['body']}", flush=True)
    
    # Also try GET without challengeId
    print(f"\n[GET] {api_url} (no params)...", flush=True)
    puzzle_get2 = page.evaluate(f"""() => {{
        return fetch('{api_url}', {{
            method: 'GET', credentials: 'include',
        }}).then(async r => {{
            const body = await r.text();
            return {{status: r.status, body: body.substring(0, 300)}};
        }});
    }}""")
    print(f"  Status: {puzzle_get2['status']}", flush=True)
    print(f"  Body: {puzzle_get2['body']}", flush=True)
    
    time.sleep(2)
    browser.close()
