"""Check PX cookies and try forcing Arkose enforcement manually."""
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
    time.sleep(8)
    
    # Check ALL cookies (including HttpOnly) via Playwright API
    all_cookies = page.context.cookies()
    px_cookies = [c for c in all_cookies if '_px' in c['name'].lower()]
    print(f"[*] All cookies: {len(all_cookies)}", flush=True)
    for c in all_cookies:
        if '_px' in c['name'].lower() or c['name'] in ['.ROBLOSECURITY', '.RBXID', 'RBXSessionTracker']:
            print(f"  {c['name']}: {c['value'][:50]}... httpOnly={c.get('httpOnly', False)}", flush=True)
    if not px_cookies:
        print("  (no _px cookies found)", flush=True)
    
    # Also check via JS
    js_cookies = page.evaluate("""() => {
        const c = document.cookie.split(';').map(x => x.trim().split('='));
        const result = {};
        for (const [k,v] of c) {
            if (k.startsWith('_px')) result[k] = v.substring(0, 80);
        }
        return result;
    }""")
    print(f"[*] JS-visible PX cookies: {json.dumps(js_cookies)[:300]}", flush=True)
    
    # Check PX global variables
    px_globals = page.evaluate("""() => {
        const r = {};
        if (window._px) r._px = typeof window._px;
        if (window._pxAppId) r._pxAppId = window._pxAppId;
        if (window._pxVideo) r._pxVideo = typeof window._pxVideo;
        if (window.PX) {
            r.PX_keys = Object.keys(window.PX);
            if (window.PX.getCaptchaToken) r.hasGetCaptchaToken = true;
            if (window.PX.getEnforcement) r.hasGetEnforcement = true;
            if (window.PX.setChallenge) r.hasSetChallenge = true;
        }
        return r;
    }""")
    print(f"[*] PX globals: {json.dumps(px_globals)[:400]}", flush=True)
    
    # Check for existing Arkose/game-core iframes
    print(f"[*] Frames ({len(page.frames)}):", flush=True)
    for f in page.frames:
        url = f.url[:120]
        if 'arkose' in url or 'game-core' in url or 'funcaptcha' in url or 'challenge' in url:
            print(f"  *** {f.url}", flush=True)
        else:
            print(f"  {url}", flush=True)
    
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
        
        if chal_meta_b64:
            pad = len(chal_meta_b64) % 4
            if pad:
                chal_meta_b64 += '=' * (4 - pad)
            meta = json.loads(base64.b64decode(chal_meta_b64))
            sp = meta.get('sharedParameters', {})
            generic_id = sp.get('genericChallengeId', '')
            print(f"[+] genericChallengeId: {generic_id}", flush=True)
    except Exception as e:
        print(f"[-] No auth: {e}", flush=True)
    
    time.sleep(3)
    
    # Check cookies after login click
    after_cookies = page.context.cookies()
    px_after = [c for c in after_cookies if '_px' in c['name'].lower()]
    print(f"[*] Cookies after login: {len(after_cookies)}, _px: {len(px_after)}", flush=True)
    for c in px_after:
        print(f"  {c['name']}: {c['value'][:60]}... domain={c.get('domain','')}", flush=True)
    if not px_after:
        print("  (no _px cookies after login either)", flush=True)
    
    # Try to load Arkose enforcement manually
    print("[*] Attempting manual Arkose enforcement...", flush=True)
    
    # Try calling PX.setChallenge if it exists
    has_set_challenge = page.evaluate("typeof window.PX?.setChallenge === 'function'")
    print(f"[*] PX.setChallenge exists: {has_set_challenge}", flush=True)
    
    if has_set_challenge:
        result = page.evaluate("""() => {
            try {
                window.PX.setChallenge({
                    challengeId: 'test',
                    metadata: '{}'
                });
                return 'called';
            } catch(e) {
                return 'error: ' + e.message;
            }
        }""")
        print(f"[*] PX.setChallenge result: {result}", flush=True)
    
    time.sleep(3)
    
    # Check frames again
    print(f"[*] Frames after attempt ({len(page.frames)}):", flush=True)
    for f in page.frames:
        if 'arkose' in f.url or 'game-core' in f.url or 'funcaptcha' in f.url or 'challenge' in f.url or 'enforcement' in f.url:
            print(f"  *** {f.url}", flush=True)
    
    page.screenshot(path="cookies_check.png")
    time.sleep(10)
    browser.close()
