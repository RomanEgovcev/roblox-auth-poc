"""Load api.js properly with data-callback to start enforcement."""
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
    
    # Define callback + load api.js with data-callback attribute
    print("[1] Loading api.js with data-callback...", flush=True)
    result = page.evaluate("""() => {
        return new Promise((resolve) => {
            // Define the callback that receives the API
            window.__myArkoseCallback = function(api) {
                console.log('Arkose API received!', Object.keys(api));
                window.__arkoseApi = api;
                resolve(true);
            };
            
            // Create script with data-callback
            const script = document.createElement('script');
            script.src = 'https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js';
            script.setAttribute('data-callback', '__myArkoseCallback');
            document.head.appendChild(script);
            
            // Timeout after 10s
            setTimeout(() => resolve(false), 10000);
        });
    }""")
    print(f"  Loaded: {result}", flush=True)
    
    # Check if API is available
    api_info = page.evaluate("""() => {
        const api = window.__arkoseApi;
        if (!api) return {error: 'API not received'};
        
        const info = {keys: Object.keys(api).slice(0, 20)};
        for (const k of Object.keys(api).slice(0, 20)) {
            info[k] = typeof api[k];
            if (typeof api[k] === 'function') {
                info[k + '_str'] = api[k].toString().substring(0, 150);
            }
        }
        return info;
    }""")
    print(f"  API: {json.dumps(api_info, indent=2)[:1000]}", flush=True)
    
    # If API received, try to call run() to start enforcement
    if api_info.get('run') == 'function':
        print("\n[2] Calling api.run() to create enforcement...", flush=True)
        page.evaluate("""async () => {
            try {
                const api = window.__arkoseApi;
                console.log('Calling api.run()...');
                const result = api.run();
                console.log('api.run() returned:', result);
                window.__arkoseRunResult = result;
            } catch(e) {
                console.error('api.run() error:', e);
                window.__arkoseRunError = e.message;
            }
        }""")
        time.sleep(5)
        
        # Check for enforcement frame
        print("[3] Checking for enforcement...", flush=True)
        for fi, f in enumerate(page.frames):
            print(f"  [{fi}] {f.url[:200]}", flush=True)
        
        # Wait more for game-core
        for i in range(30):
            for f in page.frames:
                if 'game-core' in f.url:
                    print(f"  [+] Game-core at {i*0.5:.0f}s!", flush=True)
                    state = f.evaluate("""() => ({
                        imgs: document.querySelectorAll('img').length,
                        bodyLen: document.body?.innerHTML?.length || 0,
                    })""", timeout=5000)
                    print(f"  GC: {json.dumps(state)}", flush=True)
                    break
            time.sleep(0.5)
    
    time.sleep(5)
    browser.close()
