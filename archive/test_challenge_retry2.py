"""Retry login with fresh CSRF for each attempt."""
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
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[60:120]}" if any(x in r.url for x in ['auth', 'login', 'challenge']) else "", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    def get_csrf():
        return page.evaluate(f"""() => {{
            return fetch('https://auth.roblox.com/v2/login', {{
                method: 'POST', credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
            }}).then(r => r.headers.get('x-csrf-token'));
        }}""")
    
    csrf = get_csrf()
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
                resolve({{status: xhr.status, headers: headers, body: xhr.responseText.substring(0, 300)}});
            }};
            xhr.onerror = () => resolve({{error: `XHR onerror readyState=${{xhr.readyState}} status=${{xhr.status}}`}});
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
    
    # Get fresh CSRF
    csrf2 = get_csrf()
    print(f"\nCSRF2: {csrf2}", flush=True)
    
    # Retry with fresh CSRF + challenge id
    print(f"\n[2] Retry with fresh CSRF + challenge-id...", flush=True)
    retry = page.evaluate(f"""() => {{
        return new Promise((resolve) => {{
            const xhr = new XMLHttpRequest();
            xhr.open('POST', 'https://auth.roblox.com/v2/login', true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.setRequestHeader('x-csrf-token', '{csrf2}');
            xhr.setRequestHeader('rblx-challenge-id', '{chall_id}');
            xhr.setRequestHeader('rblx-challenge-type', '{chall_type}');
            xhr.withCredentials = true;
            xhr.onload = function() {{
                const headers = {{}};
                xhr.getAllResponseHeaders().trim().split('\\n').forEach(h => {{
                    const [k, ...v] = h.split(':');
                    if (k && v.length) headers[k.trim().toLowerCase()] = v.join(':').trim();
                }});
                resolve({{status: xhr.status, headers: headers, body: xhr.responseText.substring(0, 500)}});
            }};
            xhr.onerror = () => resolve({{error: `onerror ${{xhr.status}}`}});
            xhr.send(JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}));
        }});
    }}""")
    print(f"  Status: {retry.get('status', retry.get('error', 'FAIL'))}", flush=True)
    print(f"  Body: {retry.get('body', '')[:300]}", flush=True)
    
    # Check if it worked
    if retry.get('status') == 200:
        print("\n  *** LOGIN SUCCESSFUL! ***", flush=True)
    elif retry.get('status') == 403:
        body_text = retry.get('body', '')
        print(f"  Still 403: {body_text[:200]}", flush=True)
        new_chall = retry.get('headers', {}).get('rblx-challenge-id', '')
        if new_chall:
            print(f"  New challenge: {new_chall} ({retry.get('headers', {}).get('rblx-challenge-type', '')})", flush=True)
    
    time.sleep(2)
    browser.close()
