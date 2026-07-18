"""Explore Arkose client API and try to create enforcement."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[:200]}", flush=True) if 'arkoselabs' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Load api.js
    print("[1] Loading api.js...", flush=True)
    page.evaluate("""() => {
        return new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = 'https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js';
            s.onload = () => resolve(true);
            s.onerror = () => reject(new Error('fail'));
            document.head.appendChild(s);
        });
    }""")
    time.sleep(1)
    
    # Explore the API
    print("[2] Exploring arkoseLabsClientApia87b051f...", flush=True)
    api_info = page.evaluate("""() => {
        const apiKey = Object.keys(window).find(k => k.startsWith('arkoseLabsClient'));
        const api = window[apiKey];
        if (!api) return {error: 'API not found'};
        
        const info = {};
        
        // Get all keys and methods
        const keys = Object.keys(api);
        info.keys = keys.slice(0, 30);
        
        // Check for specific methods
        const methodNames = ['setup', 'init', 'run', 'create', 'start', 'setConfig', 'getToken', 
            'onready', 'ready', 'bind', 'render', 'display', 'show', 'enforcement', 'challenge',
            'setPublicKey', 'configure'];
        for (const name of methodNames) {
            if (typeof api[name] !== 'undefined') {
                info['has_' + name] = true;
                info['type_' + name] = typeof api[name];
                if (typeof api[name] === 'function') {
                    info[name + '_str'] = api[name].toString().substring(0, 200);
                }
            }
        }
        
        // Check if there are nested objects
        const objectKeys = keys.filter(k => typeof api[k] === 'object' && api[k] !== null);
        info.objectKeys = objectKeys;
        for (const k of objectKeys.slice(0, 5)) {
            const nested = Object.keys(api[k]);
            info['nested_' + k] = nested.slice(0, 20);
        }
        
        return info;
    }""")
    print(f"  API info: {json.dumps(api_info, indent=2)[:1500]}", flush=True)
    
    # Try calling any enforcement-related method
    print("\n[3] Trying to initialize enforcement...", flush=True)
    init_result = page.evaluate("""async () => {
        const apiKey = Object.keys(window).find(k => k.startsWith('arkoseLabsClient'));
        const api = window[apiKey];
        const results = {};
        
        // Try calling the API as a function
        if (typeof api === 'function') {
            try {
                results.callResult = api({});
                results.callResultType = typeof results.callResult;
                if (results.callResult && typeof results.callResult.then === 'function') {
                    results.callResolved = await results.callResult;
                }
            } catch(e) {
                results.callError = e.message;
            }
        }
        
        // Try to find the enforcement frame
        results.frames_before = document.querySelectorAll('iframe').length;
        
        return results;
    }""")
    print(f"  Init: {json.dumps(init_result)[:400]}", flush=True)
    
    # Check frames and requests now
    print("\n[4] Status after API load...", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  Frames: [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(5)
    browser.close()
