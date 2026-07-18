"""Retry login with challenge headers (skip solving since eligibleMethods is empty)."""
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
    
    # Get challenge
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
                resolve({{status: xhr.status, headers: headers}});
            }};
            xhr.onerror = () => resolve({{error: 'XHR failed'}});
            xhr.send(JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}));
        }});
    }}""")
    print(f"\n[1] Login: {chall_data.get('status', 'FAIL')}", flush=True)
    
    chall_id = chall_data.get('headers', {}).get('rblx-challenge-id', '')
    chall_type = chall_data.get('headers', {}).get('rblx-challenge-type', '')
    chall_meta_b64 = chall_data.get('headers', {}).get('rblx-challenge-metadata', '')
    print(f"  Challenge: {chall_id} ({chall_type})", flush=True)
    
    if chall_meta_b64:
        meta = json.loads(base64.b64decode(chall_meta_b64).decode())
        em = meta.get('sharedParameters', {}).get('eligibleMethods', [])
        print(f"  eligibleMethods: {em}", flush=True)
    
    # Retry login with challenge ID header (trivially solved since eligibleMethods empty)
    print(f"\n[2] Retry login with challenge-id header...", flush=True)
    retry = page.evaluate(f"""() => {{
        return new Promise((resolve) => {{
            const xhr = new XMLHttpRequest();
            xhr.open('POST', 'https://auth.roblox.com/v2/login', true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.setRequestHeader('x-csrf-token', '{csrf}');
            xhr.setRequestHeader('rblx-challenge-id', '{chall_id}');
            xhr.setRequestHeader('rblx-challenge-solution', '');
            xhr.setRequestHeader('rblx-challenge-type', '{chall_type}');
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
    print(f"  Status: {retry.get('status', 'FAIL')}", flush=True)
    print(f"  Body: {retry.get('body', '')[:200]}", flush=True)
    
    # Try with redemption-token header too
    print(f"\n[3] Retry with redemption token header...", flush=True)
    retry2 = page.evaluate(f"""() => {{
        return new Promise((resolve) => {{
            const xhr = new XMLHttpRequest();
            xhr.open('POST', 'https://auth.roblox.com/v2/login', true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.setRequestHeader('x-csrf-token', '{csrf}');
            xhr.setRequestHeader('rblx-challenge-id', '{chall_id}');
            xhr.setRequestHeader('rblx-challenge-redemption-token', '');
            xhr.setRequestHeader('rblx-challenge-type', '{chall_type}');
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
    print(f"  Status: {retry2.get('status', 'FAIL')}", flush=True)
    print(f"  Body: {retry2.get('body', '')[:200]}", flush=True)
    
    time.sleep(2)
    browser.close()
