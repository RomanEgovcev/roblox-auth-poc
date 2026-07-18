"""Use PX-loaded Arkose API to create enforcement and capture challenge."""
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
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[:200]}", flush=True) if 'arkoselabs' in r.url or 'auth.roblox.com' in r.url or '/fc/' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Fill credentials
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Set callback before PX triggers
    print("[1] Setting up PX callback...", flush=True)
    page.evaluate("""() => {
        window.__pxArkoseApi = null;
        window.__pxArkoseCallback = function(api) {
            window.__pxArkoseApi = api;
        };
    }""")
    
    # Trigger PX via dispatchEvent
    print("[2] dispatchEvent click...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        for (let i = 0; i < 3; i++)
            btn.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',bubbles:true}));
        btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
    }""")
    
    # Wait for API object to be set by PX
    print("[3] Waiting for API...", flush=True)
    api_ready = None
    for i in range(30):
        ready = page.evaluate("typeof window.__pxArkoseApi !== 'undefined'")
        if ready:
            print(f"  API ready at {i*0.5:.0f}s!", flush=True)
            api_ready = True
            break
        time.sleep(0.5)
    
    if not api_ready:
        print("  API not ready after 15s.", flush=True)
        browser.close()
        exit()
    
    # Get API info
    api_info = page.evaluate("""() => {
        const api = window.__pxArkoseApi;
        if (!api) return {error: 'no api'};
        
        return {
            keys: Object.keys(api).slice(0, 10),
            hasConfig: typeof api.getConfig === 'function',
            hasRun: typeof api.run === 'function',
            config: api.getConfig ? JSON.stringify(api.getConfig()).substring(0, 500) : null,
            version: api.version,
        };
    }""")
    print(f"  API: {json.dumps(api_info, indent=2)[:600]}", flush=True)
    
    # Check if enforcement was auto-created by PX
    print("\n[4] Checking for auto-created enforcement...", flush=True)
    for fi, f in enumerate(page.frames):
        if 'enforcement.' in f.url:
            print(f"  [+] Enforcement: {f.url[:120]}", flush=True)
    
    # Run API.run() if enforcement not created
    has_enf = any('enforcement.' in f.url for f in page.frames)
    if not has_enf:
        print("\n[5] Calling api.run()...", flush=True)
        page.evaluate("window.__pxArkoseApi.run()")
        print("  run() called, waiting 30s...", flush=True)
        
        for i in range(60):
            for f in page.frames:
                if 'enforcement.' in f.url:
                    print(f"  [+] Enforcement at {i*0.5:.0f}s!", flush=True)
                    has_enf = True
                    break
            if has_enf:
                break
            time.sleep(0.5)
    
    if has_enf:
        time.sleep(3)
        # Wait for game-core
        print("\n[6] Waiting for game-core...", flush=True)
        gc = None
        for i in range(60):
            for f in page.frames:
                if 'game-core' in f.url:
                    gc = f
                    print(f"  [+] Game-core at {i*0.5:.0f}s!", flush=True)
                    break
            if gc:
                break
            time.sleep(0.5)
        
        if gc:
            time.sleep(3)
            state = gc.evaluate("""() => ({
                imgs: document.querySelectorAll('img').length,
                bodyLen: document.body?.innerHTML?.length || 0,
                bodyPreview: document.body?.innerHTML?.substring(0, 800) || '',
            })""")
            print(f"  GC: {json.dumps(state)[:800]}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(5)
    browser.close()
