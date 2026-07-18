"""Intercept auth 403 and inject eligibleMethods to trigger captcha."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")
patched = patched.replace("new EvalError", "new Error")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    
    auth_intercepted = [False]
    
    def intercept(route):
        url = route.request.url
        
        # Always handle main.min.js
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
            return
        
        # Intercept auth responses
        if 'auth.roblox.com' in url and '/v2/login' in url and route.request.method == 'POST':
            # Let the request go through, then modify the response
            route.continue_()
            return
        
        route.continue_()
    
    page.route("**/*", intercept)
    
    # Intercept auth response at the response level
    def modify_auth_response(response):
        if 'auth.roblox.com' in response.url and '/v2/login' in response.url and response.status == 403:
            print("[*] Intercepting 403 response to modify challenge...", flush=True)
            headers = dict(response.headers)
            chal_meta_b64 = headers.get('rblx-challenge-metadata', '')
            if chal_meta_b64:
                try:
                    pad = len(chal_meta_b64) % 4
                    if pad:
                        chal_meta_b64 += '=' * (4 - pad)
                    meta = json.loads(base64.b64decode(chal_meta_b64))
                    # Modify eligibleMethods
                    sp = meta.get('sharedParameters', {})
                    sp['eligibleMethods'] = ['captcha', 'proofofwork']
                    sp['renderNativeChallenge'] = True
                    meta['sharedParameters'] = sp
                    
                    # Re-encode
                    new_meta_b64 = base64.b64encode(json.dumps(meta).encode()).decode()
                    new_meta_b64 = new_meta_b64.rstrip('=')
                    
                    # We can't modify response headers directly in sync API
                    print(f"[+] Would set eligibleMethods to ['captcha', 'proofofwork']", flush=True)
                    print(f"[+] New metadata: {json.dumps(meta, indent=2)[:300]}", flush=True)
                    auth_intercepted[0] = True
                    
                except Exception as e:
                    print(f"[-] Error: {e}", flush=True)
    
    page.on("response", modify_auth_response)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        resp = response_info.value
        print(f"[+] Auth: {resp.status}", flush=True)
        
    except Exception as e:
        print(f"[-] No auth: {e}", flush=True)
    
    time.sleep(5)
    
    # Check frames and PX state
    px_info = page.evaluate("""() => {
        if (!window.PX) return 'PX is null';
        const keys = Object.getOwnPropertyNames(window.PX);
        const result = {};
        keys.forEach(k => { result[k] = typeof window.PX[k]; });
        return result;
    }""")
    print(f"PX properties: {json.dumps(px_info)[:500]}", flush=True)
    
    frames = page.frames
    arkose = [f for f in frames if 'arkose' in f.url]
    enforcement = [f for f in frames if 'enforcement' in f.url]
    print(f"Frames: {len(frames)}, arkose: {len(arkose)}", flush=True)
    for f in frames:
        url = f.url[:120]
        if 'roblox' not in url:
            print(f"  {url}", flush=True)
    
    page.screenshot(path="inject_eligible.png")
    time.sleep(10)
    browser.close()
