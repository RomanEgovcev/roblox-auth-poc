"""Call setConfig then run to initialize Arkose enforcement."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[:200]}", flush=True) if 'arkoselabs' in r.url or 'auth.roblox.com' in r.url or '/fc/' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Load api.js with data-callback
    print("[1] Loading api.js...", flush=True)
    page.evaluate("""() => {
        return new Promise((resolve) => {
            window.__arkoseReady = function(api) {
                window.__arkoseApi = api;
                resolve(api);
            };
            const s = document.createElement('script');
            s.src = 'https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js';
            s.setAttribute('data-callback', '__arkoseReady');
            document.head.appendChild(s);
            setTimeout(() => resolve(null), 15000);
        });
    }""")
    time.sleep(2)
    
    # First setConfig to initialize
    print("[2] Calling setConfig...", flush=True)
    config_result = page.evaluate("""async () => {
        const api = window.__arkoseApi;
        if (!api) return {error: 'no api'};
        
        try {
            // setConfig with basic options
            const result = api.setConfig({
                publicKey: '476068BF-9607-4799-B53D-966BE98E2B81',
            });
            console.log('setConfig result:', result);
            return {setConfigCalled: true, result: String(result)};
        } catch(e) {
            return {error: e.message, stack: e.stack?.substring(0, 200)};
        }
    }""")
    print(f"  setConfig: {json.dumps(config_result)[:400]}", flush=True)
    time.sleep(3)
    
    # Check state
    state = page.evaluate("""() => {
        try {
            const api = window.__arkoseApi;
            const cfg = api ? api.getConfig() : null;
            return {
                hasApi: !!api,
                config: cfg ? JSON.stringify(cfg).substring(0, 300) : null,
            };
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"  State: {json.dumps(state)[:400]}", flush=True)
    
    # Now call run
    print("\n[3] Calling run...", flush=True)
    page.evaluate("""() => {
        const api = window.__arkoseApi;
        if (api) api.run();
    }""")
    time.sleep(5)
    
    # Check for enforcement frame
    print("[4] Checking for enforcement...", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    # Wait more
    print("\n[5] Waiting 30s for enforcement...", flush=True)
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
    
    time.sleep(3)
    browser.close()
