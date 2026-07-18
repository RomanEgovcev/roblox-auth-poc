"""Intercept PX.setChallenge via Proxy to inject eligibleMethods."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")
patched = patched.replace("new EvalError", "new Error")

INTERCEPT_JS = """
// Intercept PX.setChallenge to modify metadata
const origDefineProp = Object.defineProperty;
let realSetChallenge = null;

// Watch for PX.setChallenge being defined
Object.defineProperty = function(obj, prop, desc) {
    if (obj === window.PX && prop === 'setChallenge' && 'value' in desc) {
        realSetChallenge = desc.value;
        // Replace with our wrapper
        return origDefineProp.call(Object, obj, prop, {
            value: function(data) {
                // Modify metadata to include captcha method
                try {
                    if (data && data.metadata) {
                        let meta = JSON.parse(atob(data.metadata));
                        if (meta.sharedParameters) {
                            meta.sharedParameters.eligibleMethods = ['captcha', 'proofofwork'];
                            meta.sharedParameters.renderNativeChallenge = true;
                            data.metadata = btoa(JSON.stringify(meta)).replace(/=/g, '');
                            console.log('[PX] Modified eligibleMethods to include captcha');
                        }
                    }
                } catch(e) {
                    console.log('[PX] Error modifying challenge:', e.message);
                }
                return realSetChallenge.call(this, data);
            },
            writable: true,
            configurable: true,
            enumerable: true
        });
    }
    return origDefineProp.call(Object, obj, prop, desc);
};
"""

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.add_init_script(INTERCEPT_JS)
    
    def intercept_route(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept_route)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        resp = response_info.value
        print(f"[+] Auth: {resp.status}", flush=True)
        
        # Check setChallenge was intercepted
        status = page.evaluate("""() => {
            if (!window.PX || !window.PX.setChallenge) return 'no setChallenge';
            const src = window.PX.setChallenge.toString();
            return 'intercepted: ' + (src.includes('[PX]') ? 'yes' : 'no');
        }""")
        print(f"[*] {status}", flush=True)
        
        time.sleep(5)
        
        # Check for frames
        frames = page.frames
        arkose = [f for f in frames if 'arkose' in f.url]
        enforcement = [f for f in frames if 'enforcement' in f.url]
        print(f"Frames: {len(frames)}, arkose: {len(arkose)}", flush=True)
        for f in frames:
            if f.url != 'about:blank' and 'roblox' not in f.url:
                print(f"  {f.url[:120]}", flush=True)
        
    except Exception as e:
        print(f"[-] No auth: {e}", flush=True)
    
    page.screenshot(path="intercept_setchallenge.png")
    time.sleep(10)
    browser.close()
