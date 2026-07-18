"""Use XMLHttpRequest to bypass PX fetch interception."""
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
    
    # Get CSRF
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF: {csrf}", flush=True)
    
    # Get challenge via XHR (bypasses PX fetch interception)
    print(f"\n[1] Login via XHR...", flush=True)
    chall_data = page.evaluate(f"""() => {{
        return new Promise((resolve, reject) => {{
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
                resolve({{
                    status: xhr.status,
                    headers: headers,
                    body: xhr.responseText.substring(0, 300),
                }});
            }};
            xhr.onerror = function() {{ reject('XHR failed'); }};
            xhr.send(JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}));
        }});
    }}""")
    print(f"  Status: {chall_data['status']}", flush=True)
    
    chall_id = chall_data.get('headers', {}).get('rblx-challenge-id', '')
    chall_type = chall_data.get('headers', {}).get('rblx-challenge-type', '')
    chall_meta_b64 = chall_data.get('headers', {}).get('rblx-challenge-metadata', '')
    
    print(f"  Challenge: {chall_id} ({chall_type})", flush=True)
    
    if chall_meta_b64:
        decoded = base64.b64decode(chall_meta_b64).decode('utf-8')
        meta = json.loads(decoded)
        print(f"  sessionId: {meta.get('sessionId')}", flush=True)
        sp = meta.get('sharedParameters', {})
        print(f"  eligibleMethods: {sp.get('eligibleMethods')}", flush=True)
        print(f"  genericChallengeId: {sp.get('genericChallengeId')}", flush=True)
    
    # Try XHR to challenge API
    if chall_id:
        print(f"\n[2] GET challenge via XHR...", flush=True)
        detail = page.evaluate(f"""() => {{
            return new Promise((resolve) => {{
                const xhr = new XMLHttpRequest();
                xhr.open('GET', 'https://auth.roblox.com/v1/challenge/{chall_id}', true);
                xhr.withCredentials = true;
                xhr.onload = function() {{
                    resolve({{status: xhr.status, body: xhr.responseText.substring(0, 500)}});
                }};
                xhr.onerror = function() {{ resolve({{error: 'XHR failed'}}); }};
                xhr.send();
            }});
        }}""")
        print(f"  Status: {detail['status']}", flush=True)
        print(f"  Body: {detail['body'][:500]}", flush=True)
        
        # Try POST challenge solution
        print(f"\n[3] POST challenge solution via XHR...", flush=True)
        solution = page.evaluate(f"""() => {{
            return new Promise((resolve) => {{
                const xhr = new XMLHttpRequest();
                xhr.open('POST', 'https://auth.roblox.com/v1/challenge/{chall_id}', true);
                xhr.setRequestHeader('Content-Type', 'application/json');
                xhr.withCredentials = true;
                xhr.onload = function() {{
                    const headers = {{}};
                    xhr.getAllResponseHeaders().trim().split('\\n').forEach(h => {{
                        const [k, ...v] = h.split(':');
                        if (k && v.length) headers[k.trim().toLowerCase()] = v.join(':').trim();
                    }});
                    resolve({{
                        status: xhr.status,
                        headers: headers,
                        body: xhr.responseText.substring(0, 300),
                    }});
                }};
                xhr.onerror = function() {{ resolve({{error: 'XHR failed'}}); }};
                xhr.send(JSON.stringify({{challengeId: '{chall_id}', challengeType: '{chall_type}'}}));
            }});
        }}""")
        print(f"  Status: {solution['status']}", flush=True)
        token = solution.get('headers', {}).get('rblx-challenge-redemption-token', '')
        print(f"  Redemption token: {token}", flush=True)
        if not token:
            print(f"  Body: {solution.get('body', '')[:300]}", flush=True)
            print(f"  All headers: {json.dumps(dict(solution.get('headers', {})))}", flush=True)
    
    time.sleep(2)
    browser.close()
