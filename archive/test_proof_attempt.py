"""Patched PX + try to fulfill proofofwork challenge via GET."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")
patched = patched.replace("new EvalError", "new Error")

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
"""

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080},
        locale='en-US',
    )
    page = context.new_page()
    page.add_init_script(STEALTH_JS)
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login & waiting for auth response...", flush=True)
    
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        resp = response_info.value
        print(f"[+] Auth response: {resp.status}", flush=True)
        
        headers = dict(resp.headers)
        chal_type = headers.get('rblx-challenge-type', '')
        chal_id = headers.get('rblx-challenge-id', '')
        chal_meta_b64 = headers.get('rblx-challenge-metadata', '')
        csrf = headers.get('x-csrf-token', '')
        
        print(f"[+] Type: {chal_type}, ID: {chal_id[:30] if chal_id else 'N/A'}...", flush=True)
        
        # Decode metadata
        meta = None
        if chal_meta_b64:
            try:
                pad = len(chal_meta_b64) % 4
                if pad:
                    chal_meta_b64 += '=' * (4 - pad)
                meta = json.loads(base64.b64decode(chal_meta_b64))
                sp = meta.get('sharedParameters', {})
                print(f"[+] eligibleMethods: {sp.get('eligibleMethods', 'N/A')}", flush=True)
                print(f"[+] sessionId: {meta.get('sessionId', '')[:30]}...", flush=True)
            except Exception as e:
                print(f"[-] Decode: {e}", flush=True)
        
        # Try: 1) GET request with challenge headers
        #        2) Retry POST with empty challenge body
        #        3) Different challenge approaches
        results = {}
        
        # Strategy 1: GET with challenge headers
        try:
            r1 = page.evaluate(f"""() => {{
                return fetch('https://auth.roblox.com/v2/login', {{
                    method: 'GET',
                    headers: {{
                        'rblx-challenge-id': '{chal_id}',
                        'rblx-challenge-metadata': '{chal_meta_b64}'
                    }}
                }}).then(r => r.status);
            }}""")
            results['GET'] = r1
            print(f"[+] GET challenge result: {r1}", flush=True)
        except Exception as e:
            results['GET'] = str(e)
        
        # Strategy 2: POST with challenge body appended
        if meta:
            try:
                r2 = page.evaluate(f"""() => {{
                    return fetch('https://auth.roblox.com/v2/login', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            challengeId: '{chal_id}',
                            challengeMetadata: '{chal_meta_b64}',
                            sessionId: '{meta["sessionId"]}'
                        }})
                    }}).then(async r => ({{
                        status: r.status,
                        text: await r.text().catch(() => '')
                    }}));
                }}""")
                results['POST-challenge'] = r2
                print(f"[+] POST challenge result: {json.dumps(r2)[:200]}", flush=True)
            except Exception as e:
                results['POST-challenge'] = str(e)
        
        print(f"[+] All results: {json.dumps(results)[:500]}", flush=True)
        
    except Exception as e:
        print(f"[-] Error: {e}", flush=True)
    
    page.screenshot(path="proof_attempt.png")
    time.sleep(10)
    browser.close()
