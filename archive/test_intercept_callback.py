"""Intercept PX's api.js callback name using MutationObserver."""
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
    
    # Use MutationObserver to detect when PX adds the api.js script
    # Then read its data-callback and set up our callback
    print("[1] Setting up MutationObserver for api.js script...", flush=True)
    
    page.evaluate("""() => {
        // Create a promise that resolves with the callback name
        window.__apiJsCallbackPromise = new Promise((resolve) => {
            const observer = new MutationObserver((mutations) => {
                for (const mutation of mutations) {
                    for (const node of mutation.addedNodes) {
                        if (node.tagName === 'SCRIPT' && 
                            node.src && node.src.includes('api.js')) {
                            const callback = node.getAttribute('data-callback');
                            if (callback) {
                                console.log('Found api.js callback:', callback);
                                // Set up our callback with PX's name
                                window[callback] = function(api) {
                                    console.log('Arkose API received via callback:', callback);
                                    window.__arkoseApi = api;
                                };
                                resolve(callback);
                                observer.disconnect();
                                return;
                            }
                        }
                    }
                }
            });
            observer.observe(document.head, { childList: true, subtree: true });
            
            // Timeout after 30s
            setTimeout(() => resolve(null), 30000);
        });
    }""")
    
    # Trigger PX
    print("[2] dispatchEvent click to trigger PX...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        if (btn) {
            for (let i = 0; i < 3; i++)
                btn.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',bubbles:true}));
            btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
        }
    }""")
    
    # Wait for PX to add api.js script
    print("[3] Waiting for PX to add api.js...", flush=True)
    callback_name = page.evaluate("""() => {
        // Wait for the promise
        return window.__apiJsCallbackPromise;
    }""")
    print(f"  Callback name: {callback_name}", flush=True)
    
    if callback_name:
        # Wait for API to be set
        print("[4] Waiting for API object...", flush=True)
        for i in range(30):
            has_api = page.evaluate("!!window.__arkoseApi")
            if has_api:
                print(f"  API ready at {i*0.5:.0f}s!", flush=True)
                break
            time.sleep(0.5)
        
        # Get API info
        api_info = page.evaluate("""() => {
            const api = window.__arkoseApi;
            return {
                keys: Object.keys(api).slice(0, 10),
                version: api.version,
                config: api.getConfig ? JSON.stringify(api.getConfig()).substring(0, 400) : null,
            };
        }""")
        print(f"  API: {json.dumps(api_info, indent=2)[:600]}", flush=True)
        
        # Run
        print("\n[5] Calling api.run()...", flush=True)
        page.evaluate("window.__arkoseApi.run()")
        
        # Wait for enforcement
        print("  Waiting 30s for enforcement...", flush=True)
        for i in range(60):
            for f in page.frames:
                if 'enforcement.' in f.url:
                    print(f"  [+] Enforcement at {i*0.5:.0f}s!", flush=True)
                    print(f"      {f.url[:120]}", flush=True)
                    time.sleep(5)
                    for f2 in page.frames:
                        if 'game-core' in f2.url:
                            state = f2.evaluate("""() => ({
                                imgs: document.querySelectorAll('img').length,
                                bodyLen: document.body?.innerHTML?.length || 0,
                            })""", timeout=5000)
                            print(f"  GC: {json.dumps(state)}", flush=True)
                    break
            time.sleep(0.5)
    else:
        print("  No api.js script detected in 30s.", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
