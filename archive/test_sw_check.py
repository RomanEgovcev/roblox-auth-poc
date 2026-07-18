"""Check for ServiceWorker handling proofofwork + try setChallenge with real data."""
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
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(6)
    
    # Check ServiceWorkers
    sw = page.evaluate("""() => {
        return navigator.serviceWorker?.getRegistrations?.()
            .then(regs => regs.map(r => ({
                scope: r.scope,
                active: r.active?.scriptURL || null
            })))
            .catch(() => 'sw_error');
    }""")
    print(f"[*] ServiceWorkers: {sw}", flush=True)
    
    # Check for challenge handlers in page
    handlers = page.evaluate("""() => {
        const results = {};
        // Check for common challenge handler globals
        if (window.__challengeHandler) results.challengeHandler = true;
        if (window.__cf_challenge) results.cf_challenge = true;
        if (window.turnstile) results.turnstile = typeof window.turnstile;
        if (window._pxChallengeHandler) results.pxChallengeHandler = true;
        if (window.PX) {
            results.PX_api = {};
            ['getEnforcement', 'setChallenge', 'getCaptchaToken', 'renderEnforcement', 'start'].forEach(k => {
                if (typeof window.PX[k] === 'function') results.PX_api[k] = true;
            });
        }
        return results;
    }""")
    print(f"[*] Challenge handlers: {json.dumps(handlers, indent=2)}", flush=True)
    
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
        
        headers = dict(resp.headers)
        chal_meta_b64 = headers.get('rblx-challenge-metadata', '')
        chal_id = headers.get('rblx-challenge-id', '')
        
        print(f"[+] Challenge type: {headers.get('rblx-challenge-type','?')}", flush=True)
        
        # Try PX.setChallenge with real metadata
        result1 = page.evaluate(f"""() => {{
            try {{
                window.PX.setChallenge({{
                    challengeId: '{chal_id}',
                    metadata: '{chal_meta_b64}'
                }});
                return 'setChallenge OK';
            }} catch(e) {{
                return 'error: ' + e.message;
            }}
        }}""")
        print(f"[*] setChallenge: {result1}", flush=True)
        time.sleep(3)
        
        # Get request metadata for manual Arkose
        if chal_meta_b64:
            pad = len(chal_meta_b64) % 4
            if pad:
                chal_meta_b64 += '=' * (4 - pad)
            meta = json.loads(base64.b64decode(chal_meta_b64))
            sp = meta.get('sharedParameters', {})
            session_id = meta.get('sessionId', '')
            generic_id = sp.get('genericChallengeId', '')
            
            print(f"[+] sessionId: {session_id}", flush=True)
            print(f"[+] genericChallengeId: {generic_id}", flush=True)
            
            # Check: try PX.getEnforcement with challenge data
            result2 = page.evaluate(f"""() => {{
                try {{
                    let e = window.PX.getEnforcement('{chal_id}');
                    if (e) return 'getEnforcement returned: ' + JSON.stringify(Object.keys(e));
                    return 'getEnforcement returned null';
                }} catch(e) {{
                    return 'error: ' + e.message;
                }}
            }}""")
            print(f"[*] getEnforcement: {result2}", flush=True)
        
        time.sleep(3)
        
        # Check for new frames
        frames = page.frames
        arkose = [f for f in frames if 'arkose' in f.url]
        print(f"[*] Frames: {len(frames)}, arkose: {len(arkose)}", flush=True)
        for f in frames:
            if f.url != 'about:blank' and 'roblox' not in f.url:
                print(f"  {f.url[:120]}", flush=True)
        
    except Exception as e:
        print(f"[-] No auth: {e}", flush=True)
    
    page.screenshot(path="sw_check.png")
    time.sleep(10)
    browser.close()
