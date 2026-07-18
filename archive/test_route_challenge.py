"""Use page.route to bypass PX interception on challenge API."""
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
    
    # Route challenge API requests through Playwright
    challenge_result = {"done": False, "data": None}
    
    def handle_challenge(route):
        if challenge_result["done"]:
            route.continue_()
            return
        print(f"\n[route] {route.request.method} {route.request.url[:120]}", flush=True)
        challenge_result["done"] = True
        response = page.request.fetch(route.request)
        print(f"  Response: {response.status}", flush=True)
        challenge_result["data"] = {
            "status": response.status,
            "headers": dict(response.headers),
            "body": response.text()[:500],
        }
        route.fulfill(
            status=response.status,
            headers=response.headers,
            body=response.body()
        )
    
    page.route("https://auth.roblox.com/v1/challenge/**/*", handle_challenge)
    
    # Get challenge via XHR
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
    print(f"  Challenge: {chall_id} ({chall_type})", flush=True)
    
    # GET challenge
    if chall_id:
        get_result = page.evaluate(f"""() => {{
            return new Promise((resolve) => {{
                const xhr = new XMLHttpRequest();
                xhr.open('GET', 'https://auth.roblox.com/v1/challenge/{chall_id}', true);
                xhr.withCredentials = true;
                xhr.onload = function() {{
                    const headers = {{}};
                    xhr.getAllResponseHeaders().trim().split('\\n').forEach(h => {{
                        const [k, ...v] = h.split(':');
                        if (k && v.length) headers[k.trim().toLowerCase()] = v.join(':').trim();
                    }});
                    resolve({{status: xhr.status, headers: headers, body: xhr.responseText.substring(0, 500)}});
                }};
                xhr.onerror = () => resolve({{error: 'XHR failed'}});
                xhr.send();
            }});
        }}""")
        if challenge_result["data"]:
            print(f"\n[2] GET via route: {challenge_result['data']['status']}", flush=True)
            print(f"  Body: {challenge_result['data']['body']}", flush=True)
        else:
            print(f"\n[2] GET: {get_result.get('status', get_result.get('error', '?'))}", flush=True)
            print(f"  {get_result.get('body', '')}", flush=True)
        
        challenge_result["done"] = False
        
        # POST solution
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
                    resolve({{status: xhr.status, headers: headers, body: xhr.responseText.substring(0, 300)}});
                }};
                xhr.onerror = () => resolve({{error: 'XHR failed'}});
                xhr.send(JSON.stringify({{challengeId: '{chall_id}', challengeType: '{chall_type}'}}));
            }});
        }}""")
        if challenge_result["data"]:
            print(f"\n[3] POST solution via route: {challenge_result['data']['status']}", flush=True)
            d = challenge_result['data']
            print(f"  Body: {d['body']}", flush=True)
            for k, v in d['headers'].items():
                if 'token' in k.lower() or 'chall' in k.lower():
                    print(f"  {k}: {v}", flush=True)
        else:
            print(f"\n[3] POST: {solution.get('status', solution.get('error', '?'))}", flush=True)
            print(f"  {solution.get('body', '')}", flush=True)
    
    time.sleep(2)
    browser.close()
