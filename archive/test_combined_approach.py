"""Combined approach: dispatchEvent pre-load enforcement, then click login with patched PX."""
import os, time, json, base64, sys, requests

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script.replace('new Function("return this")()', "(window||self||globalThis)")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Track ALL network calls
    network_log = []
    def track_all(response):
        url = response.url
        if 'arkoselabs.roblox.com' in url or 'auth.roblox.com' in url or 'game-core' in url:
            network_log.append(f"[{response.status}] {url[:200]}")
    page.on("response", track_all)
    
    # Patch PX via route interception
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
    
    # ===== STEP 1: dispatchEvent to pre-load enforcement =====
    print("[1] dispatchEvent to pre-load enforcement (patched PX)...", flush=True)
    page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        if (btn) {
            btn.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
            btn.dispatchEvent(new PointerEvent('pointerup', {bubbles: true}));
            btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
        }
    }""")
    
    # ===== STEP 2: Wait for enforcement iframe =====
    print("[2] Waiting for enforcement iframe (up to 30s)...", flush=True)
    enf_frame = None
    for i in range(60):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                break
        if enf_frame:
            enf_url = enf_frame.url
            print(f"  [+] Enforcement at {i*0.5:.0f}s!", flush=True)
            print(f"    URL: {enf_url[:250]}", flush=True)
            break
        time.sleep(0.5)
    
    if not enf_frame:
        print("  [-] No enforcement from dispatchEvent. Trying Enter...", flush=True)
        page.keyboard.press("Enter")
        time.sleep(10)
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                enf_url = f.url
                print(f"  [+] Enforcement found after Enter: {enf_url[:200]}", flush=True)
                break
    
    if not enf_frame:
        print("  [-] No enforcement at all!", flush=True)
        browser.close()
        sys.exit(1)
    
    # ===== STEP 3: Click login to trigger auth 403 =====
    print("\n[3] Clicking login (page.click with patched PX)...", flush=True)
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        resp = response_info.value
        print(f"  [+] Auth: {resp.status}", flush=True)
    except Exception as e:
        print(f"  [-] Auth: {e}", flush=True)
        # Check if auth happened without expect_response
        auth_urls = [r for r in network_log if 'auth.roblox.com' in r]
        if auth_urls:
            print(f"  Auth responses: {auth_urls}", flush=True)
    
    # ===== STEP 4: Wait for game-core in enforcement =====
    print("\n[4] Waiting for game-core (up to 120s)...", flush=True)
    game_core_frame = None
    for i in range(240):
        # Check for game-core frame
        for f in page.frames:
            if 'game-core' in f.url:
                game_core_frame = f
                break
        
        # Check enforcement state
        try:
            enf_state = enf_frame.evaluate("""() => ({
                bodyLen: document.body?.innerHTML?.length || 0,
                iframes: document.querySelectorAll('iframe').length,
                challenge: !!document.getElementById('challenge'),
                funCaptcha: !!document.getElementById('FunCaptcha'),
            })""")
        except:
            enf_state = {}
        
        if game_core_frame:
            print(f"  [+] Game-core at {i*0.5:.0f}s!", flush=True)
            print(f"    URL: {game_core_frame.url[:200]}", flush=True)
            break
        
        if i == 20:
            # Try clicking on challenge to trigger game-core
            try:
                enf_frame.evaluate("""() => {
                    const el = document.getElementById('challenge') || document.getElementById('FunCaptcha');
                    if (el) el.click();
                }""")
            except: pass
        
        if i % 30 == 0 and i > 0:
            print(f"  [{i*0.5:.0f}s] enf: bodyLen={enf_state.get('bodyLen',0)}, iframes={enf_state.get('iframes',0)}", flush=True)
        time.sleep(0.5)
    
    # ===== STEP 5: If game-core loaded, extract data =====
    if game_core_frame:
        print("\n[5] Checking game-core elements...", flush=True)
        for i in range(15):
            gc_state = game_core_frame.evaluate("""() => ({
                canvases: document.querySelectorAll('canvas').length,
                images: document.querySelectorAll('img').length,
                buttons: document.querySelectorAll('button').length,
            })""")
            print(f"  [{i}s] {json.dumps(gc_state)}", flush=True)
            if gc_state['canvases'] > 0 or gc_state['images'] > 3:
                print(f"  [+] Captcha loaded!", flush=True)
                page.screenshot(path="captcha_loaded.png")
                break
            time.sleep(1)
    
    # ===== SUMMARY =====
    print(f"\n=== Network ({len(network_log)}) ===", flush=True)
    for r in network_log:
        print(f"  {r}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:180]}", flush=True)
    
    page.screenshot(path="combined_approach.png")
    time.sleep(15)
    browser.close()
