"""Try different challenge API endpoints."""
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
    
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF: {csrf}", flush=True)
    
    chall_data = page.evaluate(f"""() => {{
        return new Promise((resolve) => {{
            const xhr = new XMLHttpRequest();
            xhr.open('POST', 'https://auth.roblox.com/v2/login', true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.setRequestHeader('x-csrf-token', '{csrf}');
            xhr.withCredentials = true;
            xhr.onload = function() {{
                const headers = {{}};
                xhr.getAllResponseHeaders().trim().split('\\n').forEach(h => {{
                    const [k, ...v] = h.split(':');
                    if (k && v.length) headers[k.trim().toLowerCase()] = v.join(':').trim();
                }});
                resolve({{status: xhr.status, headers: headers, body: xhr.responseText.substring(0, 300)}});
            }};
            xhr.onerror = () => resolve({{error: 'XHR failed'}});
            xhr.send(JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}));
        }});
    }}""")
    print(f"\n[1] Login: {chall_data.get('status', 'FAIL')}", flush=True)
    
    chall_id = chall_data.get('headers', {}).get('rblx-challenge-id', '')
    chall_type = chall_data.get('headers', {}).get('rblx-challenge-type', '')
    chall_meta_b64 = chall_data.get('headers', {}).get('rblx-challenge-metadata', '')
    
    meta = json.loads(base64.b64decode(chall_meta_b64).decode()) if chall_meta_b64 else {}
    session_id = meta.get('sessionId', '')
    generic_id = meta.get('sharedParameters', {}).get('genericChallengeId', '')
    
    print(f"  ID: {chall_id}", flush=True)
    print(f"  Type: {chall_type}", flush=True)
    print(f"  sessionId: {session_id}", flush=True)
    print(f"  genericChallengeId: {generic_id}", flush=True)
    
    # Try various challenge endpoints
    endpoints = [
        f"https://auth.roblox.com/v1/challenge/{chall_id}",
        f"https://auth.roblox.com/v1/challenge/{chall_id}/verify",
        f"https://auth.roblox.com/v1/challenge/{generic_id}",
        f"https://challenge.roblox.com/v1/challenge/{chall_id}",
        f"https://apis.roblox.com/challenge/v1/{chall_id}",
        f"https://apis.roblox.com/challenge/v1/public/{chall_id}",
    ]
    
    for ep in endpoints:
        try:
            result = page.evaluate(f"""() => {{
                return new Promise((resolve) => {{
                    const xhr = new XMLHttpRequest();
                    xhr.open('GET', '{ep}', true);
                    xhr.withCredentials = true;
                    xhr.onload = function() {{
                        resolve({{status: xhr.status, body: xhr.responseText.substring(0, 200)}});
                    }};
                    xhr.onerror = () => resolve({{error: 'FAIL'}});
                    xhr.send();
                }});
            }}""")
            status = result.get('status', result.get('error', '?'))
            body = result.get('body', '')
            print(f"\n[GET] {ep[:100]}", flush=True)
            print(f"  {status}: {body[:150]}", flush=True)
        except Exception as e:
            print(f"\n[GET] {ep[:100]}: ERROR {e}", flush=True)
    
    time.sleep(2)
    browser.close()
