"""Get PX challenge data (oC) and pass to Arkose API."""
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
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[:200]}", flush=True) if 'arkoselabs' in r.url or 'auth.roblox.com' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Load api.js
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
    
    # Check PX's oC challenge data
    print("[2] Checking PX challenge data (oC)...", flush=True)
    oC = page.evaluate("""() => {
        try {
            if (typeof oC !== 'undefined') {
                const str = JSON.stringify(oC).substring(0, 500);
                return {exists: true, value: str, type: typeof oC};
            }
            return {exists: false};
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"  oC: {json.dumps(oC)[:400]}", flush=True)
    
    # Check PX other relevant variables
    px_vars = page.evaluate("""() => {
        const results = {};
        for (const name of ['nH', 'oC', 'nF']) {
            try {
                results[name] = typeof eval(name);
                if (typeof eval(name) !== 'undefined') {
                    results[name + '_val'] = JSON.stringify(eval(name)).substring(0, 200);
                }
            } catch(e) {
                results[name] = 'error: ' + e.message.substring(0, 50);
            }
        }
        return results;
    }""")
    print(f"  PX vars: {json.dumps(px_vars, indent=2)[:400]}", flush=True)
    
    # Check PX.setChallenge - call it with some data to see if it works
    print("\n[3] Testing PX.setChallenge...", flush=True)
    sc_result = page.evaluate("""() => {
        try {
            if (typeof PX !== 'undefined' && typeof PX.setChallenge === 'function') {
                // Test call with empty object
                PX.setChallenge({});
                return {called: true};
            }
            return {error: 'setChallenge not available'};
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"  setChallenge: {json.dumps(sc_result)}", flush=True)
    
    # Re-check oC after setChallenge
    oC2 = page.evaluate("""() => {
        try {
            if (typeof oC !== 'undefined') {
                return {exists: true, value: JSON.stringify(oC).substring(0, 500)};
            }
            return {exists: false};
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"  oC after: {json.dumps(oC2)[:400]}", flush=True)
    
    # Fill credentials and trigger a POST to get real challenge data
    print("\n[4] Triggering login POST to get challenge data...", flush=True)
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Use dispatchEvent click to trigger PX challenge
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        if (btn) {
            for (let i = 0; i < 3; i++)
                btn.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',bubbles:true}));
            btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
        }
    }""")
    time.sleep(3)
    
    # Re-check oC
    oC3 = page.evaluate("""() => {
        try {
            if (typeof oC !== 'undefined') {
                const val = oC;
                // Try to stringify
                const str = JSON.stringify(val).substring(0, 1000);
                return {exists: true, value: str, keys: val ? Object.keys(val).slice(0, 10) : []};
            }
            return {exists: false};
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"  oC after click: {json.dumps(oC3)[:500]}", flush=True)
    
    time.sleep(3)
    browser.close()
