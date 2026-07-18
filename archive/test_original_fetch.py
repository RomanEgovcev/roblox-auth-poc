"""Save original fetch/XHR before PX loads to bypass interception."""
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
    
    # Save original XHR/fetch before any page content loads
    page.add_init_script("""
        window.__originalFetch = window.fetch.bind(window);
        window.__originalXHR = window.XMLHttpRequest;
    """)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Verify originals are saved
    saved = page.evaluate("""() => ({
        hasFetch: typeof window.__originalFetch === 'function',
        hasXHR: typeof window.__originalXHR === 'function',
    })""")
    print(f"Saved originals: {saved}", flush=True)
    
    # Step 1: Get CSRF using original fetch
    csrf = page.evaluate(f"""() => {{
        return window.__originalFetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF: {csrf}", flush=True)
    
    # Step 2: Login with CSRF to get challenge (use original fetch)
    chall = page.evaluate(f"""() => {{
        return window.__originalFetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(async r => {{
            const headers = {{}};
            r.headers.forEach((v, k) => {{ headers[k] = v; }});
            const body = await r.text();
            return {{status: r.status, headers, body: body.substring(0, 300)}};
        }});
    }}""")
    print(f"\nLogin: {chall['status']}", flush=True)
    
    h = chall.get('headers', {})
    chall_id = h.get('rblx-challenge-id', '')
    chall_type = h.get('rblx-challenge-type', '')
    chall_meta_b64 = h.get('rblx-challenge-metadata', '')
    
    if not chall_id:
        print("No challenge!", flush=True)
        print(f"Headers: {json.dumps(h, indent=2)}", flush=True)
        browser.close()
        exit()
    
    print(f"Challenge: {chall_id} ({chall_type})", flush=True)
    
    if chall_meta_b64:
        meta = json.loads(base64.b64decode(chall_meta_b64 + '==').decode())
        print(f"eligibleMethods: {meta.get('sharedParameters', {}).get('eligibleMethods')}", flush=True)
    
    # Step 3: Try solving challenge with various proof values
    csrf2 = page.evaluate(f"""() => {{
        return window.__originalFetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF2: {csrf2}", flush=True)
    
    # Try plain solution values
    for label, solution in [
        ("sessionId", chall_id.split('-')[-1] if '-' in chall_id else chall_id),
        ("empty", ""),
        ("zero", "0"),
        ("true", "true"),
    ]:
        result = page.evaluate(f"""() => {{
            return window.__originalFetch('https://auth.roblox.com/v2/login', {{
                method: 'POST', credentials: 'include',
                headers: {{
                    'Content-Type': 'application/json',
                    'x-csrf-token': '{csrf2}',
                    'rblx-challenge-id': '{chall_id}',
                    'rblx-challenge-type': '{chall_type}',
                    'rblx-challenge-solution': '{solution}',
                }},
                body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
            }}).then(async r => {{
                const body = await r.text();
                const hdrs = {{}};
                r.headers.forEach((v, k) => {{ hdrs[k] = v; }});
                return {{status: r.status, headers: hdrs, body: body.substring(0, 200)}};
            }});
        }}""")
        print(f"\n  [{label}] solution='{solution[:20]}' -> {result.get('status', '?')}", flush=True)
        body = result.get('body', '')
        if result['status'] == 200:
            print(f"  *** LOGIN SUCCESS! *** Body: {body}", flush=True)
            break
        elif 'Challenge' in body:
            new_id = result.get('headers', {}).get('rblx-challenge-id', '')
            print(f"  New challenge: {new_id}", flush=True)
        else:
            print(f"  Error: {body[:100]}", flush=True)
    
    time.sleep(2)
    browser.close()
