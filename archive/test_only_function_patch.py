"""Patched PX (Function only, no EvalError patch) + check for Arkose + try manual enforcement."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

# PATCHED version — patch both new Function and EvalError
patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")
patched = patched.replace("new EvalError", "new Error")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    
    post_click_requests = []
    
    def track_all_after_click(req):
        post_click_requests.append({"url": req.url[:130], "method": req.method})
    
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
    
    # Start tracking AFTER page load
    page.on("request", track_all_after_click)
    
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
        chal_type = headers.get('rblx-challenge-type', '')
        chal_id = headers.get('rblx-challenge-id', '')
        
        print(f"[+] Type: {chal_type}, ID: {chal_id[:30] if chal_id else 'N/A'}...", flush=True)
        
        if chal_meta_b64:
            pad = len(chal_meta_b64) % 4
            if pad:
                chal_meta_b64 += '=' * (4 - pad)
            meta = json.loads(base64.b64decode(chal_meta_b64))
            sp = meta.get('sharedParameters', {})
            generic_id = sp.get('genericChallengeId', '')
            session_id = meta.get('sessionId', '')
            print(f"[+] genericChallengeId: {generic_id}", flush=True)
            print(f"[+] sessionId: {session_id}", flush=True)
            print(f"[+] eligibleMethods: {sp.get('eligibleMethods', 'N/A')}", flush=True)
            
            # Extract challenge metadata for potential manual use
            challenge_meta_b64 = chal_meta_b64
            challenge_id = chal_id
    
    except Exception as e:
        print(f"[-] No auth: {e}", flush=True)
    
    time.sleep(3)
    
    # List all requests after click
    print(f"\n=== Post-click requests ({len(post_click_requests)}) ===", flush=True)
    auth_reqs = [r for r in post_click_requests if 'auth' in r['url']]
    px_reqs = [r for r in post_click_requests if 'px' in r['url']]
    arkose_reqs = [r for r in post_click_requests if 'arkose' in r['url'] or 'funcaptcha' in r['url']]
    other = [r for r in post_click_requests if r not in auth_reqs + px_reqs + arkose_reqs]
    
    print(f"Auth: {len(auth_reqs)}", flush=True)
    for r in auth_reqs:
        print(f"  {r['method']} {r['url']}", flush=True)
    print(f"PX: {len(px_reqs)}", flush=True)
    for r in px_reqs:
        print(f"  {r['method']} {r['url']}", flush=True)
    print(f"Arkose: {len(arkose_reqs)}", flush=True)
    for r in arkose_reqs:
        print(f"  {r['method']} {r['url']}", flush=True)
    
    # Check console errors
    try:
        console_errors = []
        def on_console(msg):
            if msg.type == 'error' or msg.type == 'warning':
                console_errors.append(msg.text[:200])
        page.on("console", on_console)
        time.sleep(2)
        if console_errors:
            print(f"\nConsole errors ({len(console_errors)}):", flush=True)
            for e in console_errors[:5]:
                print(f"  {e}", flush=True)
    except:
        pass
    
    # Check frames
    frames = page.frames
    print(f"\nFrames: {len(frames)}", flush=True)
    for f in frames:
        print(f"  {f.url[:100]}", flush=True)
    
    page.screenshot(path="no_evalerror_patch.png")
    time.sleep(10)
    browser.close()
