"""CSP bypass + dispatchEvent pre-load + page.click submit."""
import os, time, json, sys, re

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Track all Arkose and auth responses
    calls = []
    page.on("response", lambda r: calls.append({
        'status': r.status, 'url': r.url[:200],
        'headers': dict(r.headers)
    }) if ('arkoselabs.roblox.com' in r.url or '/v2/login' in r.url or '/v2/user' in r.url) else None)
    
    enf_frames = []
    def track_frames(frame):
        if 'arkoselabs.roblox.com' in frame.url and 'enforcement.' in frame.url:
            enf_frames.append(frame)
            print(f"  [+] Enforcement: {frame.url[:200]}", flush=True)
    page.on("frameattached", track_frames)
    page.on("framenavigated", track_frames)
    
    print("[1] Loading page with CSP bypass...", flush=True)
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Verify CSP bypass works
    fn_test = page.evaluate("""() => {
        try { return {ok: true, result: typeof new Function("return this")()}; }
        catch(e) { return {ok: false, error: e.message}; }
    }""")
    print(f"  new Function: {fn_test}", flush=True)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Step 1: dispatchEvent click to pre-load enforcement (fast track)
    print("\n[2] dispatchEvent click (pre-load)...", flush=True)
    page.evaluate("""() => {
        document.getElementById('login-button').dispatchEvent(
            new MouseEvent('click', {bubbles: true, cancelable: true, view: window})
        );
    }""")
    
    print("  Waiting 10s for enforcement...", flush=True)
    for i in range(20):
        if len(enf_frames) > 0:
            print(f"  Found at {i*0.5:.0f}s!", flush=True)
            break
        time.sleep(0.5)
    
    if len(enf_frames) == 0:
        print("  Retrying dispatchEvent click...", flush=True)
        page.evaluate("""() => {
            document.getElementById('login-button').dispatchEvent(
                new MouseEvent('click', {bubbles: true, cancelable: true, view: window})
            );
        }""")
        time.sleep(10)
    
    if len(enf_frames) == 0:
        print("  No enforcement!", flush=True)
        browser.close()
        exit()
    
    enf = enf_frames[0]
    st_match = re.search(r'&([0-9a-f\-]{36})$', enf.url)
    token = st_match.group(1) if st_match else "none"
    print(f"  Session token: {token}", flush=True)
    
    # Wait for enforcement to fully initialize
    time.sleep(5)
    
    # Step 2: Submit form via page.click (trusted event, CSP bypassed)
    print("\n[3] page.click('#login-button') (submit)...", flush=True)
    page.click("#login-button")
    
    # Wait for auth response + game-core
    print("  Waiting for auth + game-core (30s)...", flush=True)
    auth_resp = None
    gc_found = False
    for i in range(60):
        # Check for auth response
        for c in calls:
            if '/v2/login' in c['url'] and c['status'] == 403:
                if not auth_resp:
                    auth_resp = c
                    print(f"  [+] Auth 403 at {i*0.5:.0f}s!", flush=True)
                    # Check for challenge headers
                    for k, v in auth_resp['headers'].items():
                        if 'challenge' in k.lower() or 'rblx' in k.lower():
                            print(f"    {k}: {v[:200]}", flush=True)
        
        # Check game-core in frames
        for f in page.frames:
            if 'game-core' in f.url or 'game_core' in f.url:
                if not gc_found:
                    gc_found = True
                    print(f"  [+] Game-core: {f.url[:200]}", flush=True)
        
        if auth_resp and gc_found:
            break
        time.sleep(0.5)
    
    print(f"\n  Auth 403: {auth_resp is not None}", flush=True)
    print(f"  Game-core: {gc_found}", flush=True)
    
    print(f"\n=== All frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    print(f"\n=== Key API calls ===", flush=True)
    for c in calls:
        if c['status'] in [403, 200]:
            print(f"  [{c['status']}] {c['url']}", flush=True)
    
    page.screenshot(path="csp_bypass_flow.png")
    time.sleep(10)
    browser.close()
