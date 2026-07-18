"""Deterministic: load api.js, wait for fingerprint collection, then run."""
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
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[40:160]}", flush=True) if 'arkoselabs' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Load api.js with callback
    print("[1] Loading api.js...", flush=True)
    loaded = page.evaluate("""() => {
        return new Promise((resolve) => {
            window.__arkCB = function(api) {
                window.__arkApi = api;
                console.log('API received!');
                resolve(true);
            };
            const s = document.createElement('script');
            s.src = 'https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js';
            s.setAttribute('data-callback', '__arkCB');
            document.head.appendChild(s);
            setTimeout(() => {
                console.log('API timeout');
                resolve(false);
            }, 15000);
        });
    }""")
    print(f"  Loaded: {loaded}", flush=True)
    
    if not loaded:
        print("  API load failed!", flush=True)
        browser.close()
        exit()
    
    # setConfig
    print("\n[2] setConfig...", flush=True)
    page.evaluate("""() => {
        const api = window.__arkApi;
        api.setConfig({
            publicKey: '476068BF-9607-4799-B53D-966BE98E2B81',
        });
    }""")
    
    # Wait for settings and fingerprint collection to complete
    print("[3] Waiting 10s for onReady...", flush=True)
    time.sleep(10)
    
    # Call run
    print("[4] Calling run...", flush=True)
    page.evaluate("""() => {
        const api = window.__arkApi;
        if (api) api.run();
    }""")
    
    # Wait for enforcement/game-core
    print("[5] Waiting for game-core...", flush=True)
    gc = None
    for i in range(30):
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
        })""")
        print(f"  GC: {json.dumps(state)}", flush=True)
        
        # Fill and submit form
        page.fill("input[name='username']", USER)
        page.fill("input[name='password']", PASS)
        time.sleep(1)
        
        print("\n[6] Submitting form via React onClick...", flush=True)
        btn_state = page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            if (!btn) return 'no_button';
            const pk = Object.keys(btn).find(k => k.startsWith('__reactProps'));
            if (pk && btn[pk]?.onClick) {
                btn[pk].onClick({});
                return 'submitted';
            }
            return 'no_handler';
        }""")
        print(f"  Submit: {btn_state}", flush=True)
        
        # Wait for images
        for i in range(40):
            state = gc.evaluate("""() => ({
                imgs: document.querySelectorAll('img').length,
                bodyLen: document.body?.innerHTML?.length || 0,
            })""")
            if state['imgs'] > 0:
                print(f"  [+] {state['imgs']} images at {i*0.5:.0f}s!", flush=True)
                break
            if i % 10 == 0:
                print(f"  t={i*0.5:.0f}s: {json.dumps(state)}", flush=True)
            time.sleep(0.5)
        
        print(f"  Final: {json.dumps(state)}", flush=True)
    else:
        print("  No game-core found.", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
