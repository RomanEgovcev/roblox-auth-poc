"""Wait for PX to load api.js naturally, intercept and create enforcement."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[:200]}", flush=True) if 'arkoselabs' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Set up callback BEFORE loading api.js, so when PX triggers it, we capture it
    # PX uses document.currentScript to get data-callback name
    # Let's override document.currentScript to capture any script load
    print("[1] Setting up api.js interception...", flush=True)
    
    # Set a universal callback that will be called by api.js
    page.evaluate("""() => {
        window.__pxArkoseApi = null;
        window.__pxArkoseCallback = function(api) {
            console.log('[px] Arkose API received from PX load!');
            window.__pxArkoseApi = api;
        };
    }""")
    
    # Now trigger PX
    print("[2] dispatchEvent click to trigger PX...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        for (let i = 0; i < 3; i++)
            btn.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',bubbles:true}));
        btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
    }""")
    
    time.sleep(5)
    
    # Check if PX loaded api.js
    print(f"[3] After 5s - Arkose API: {page.evaluate('typeof window.__pxArkoseApi')}", flush=True)
    print(f"  Frames:", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"    [{fi}] {f.url[:200]}", flush=True)
    
    # Wait 60s total
    print("\n[4] Waiting 60s for enforcement...", flush=True)
    t0 = time.time()
    for i in range(120):
        # Check if PX loaded api.js
        has_api = page.evaluate("typeof window.__pxArkoseApi !== 'undefined'", timeout=3000)
        if has_api:
            if i == 0 or i % 10 == 0:
                elapsed = time.time() - t0
                print(f"  [+] API available at {elapsed:.0f}s", flush=True)
        
        # Check for enforcement
        for f in page.frames:
            if 'enforcement.' in f.url:
                elapsed = time.time() - t0
                print(f"  [+] Enforcement at {elapsed:.0f}s: {f.url[:120]}", flush=True)
                break
        
        time.sleep(0.5)
    
    elapsed = time.time() - t0
    print(f"\n  Total wait: {elapsed:.0f}s", flush=True)
    
    # If API is available, try to use it
    has_api = page.evaluate("!!window.__pxArkoseApi", timeout=3000)
    if has_api:
        print(f"\n[5] API available! Checking state...", flush=True)
        state = page.evaluate("""() => {
            const api = window.__pxArkoseApi;
            const cfg = api ? api.getConfig() : null;
            return {
                keys: api ? Object.keys(api).slice(0, 10) : [],
                config: cfg ? Object.keys(cfg) : null,
            };
        }""", timeout=3000)
        print(f"  State: {json.dumps(state, indent=2)[:500]}", flush=True)
        
        # If api available but no enforcement, try running
        if not any('enforcement.' in f.url for f in page.frames):
            print("  Running api.run()...", flush=True)
            page.evaluate("window.__pxArkoseApi.run()", timeout=3000)
            time.sleep(5)
            for fi, f in enumerate(page.frames):
                print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
