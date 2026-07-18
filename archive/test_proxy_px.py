"""Proxy window.PX to intercept setChallenge before it's created."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")
patched = patched.replace("new EvalError", "new Error")

PROXY_JS = """
// Proxy window.PX to intercept setChallenge assignment
if (!window.__pxPatched) {
    window.__pxPatched = true;
    
    let _px = null;
    let _realSetChallenge = null;
    
    // Watch for window.PX being created
    Object.defineProperty(window, 'PX', {
        configurable: true,
        enumerable: true,
        get() { return _px; },
        set(val) {
            if (val && !val.__patched) {
                // Wrap setChallenge when it's assigned
                val.__patched = true;
                _px = new Proxy(val, {
                    set(target, prop, value) {
                        if (prop === 'setChallenge' && typeof value === 'function') {
                            _realSetChallenge = value;
                            target[prop] = function(data) {
                                try {
                                    if (data && data.metadata) {
                                        let meta = JSON.parse(atob(data.metadata));
                                        let sp = meta.sharedParameters || {};
                                        sp.eligibleMethods = ['captcha', 'proofofwork'];
                                        sp.renderNativeChallenge = true;
                                        meta.sharedParameters = sp;
                                        data.metadata = btoa(JSON.stringify(meta));
                                    }
                                } catch(e) {}
                                return _realSetChallenge.call(this, data);
                            };
                        } else {
                            target[prop] = value;
                        }
                        return true;
                    }
                });
            } else {
                _px = val;
            }
        }
    });
}
"""

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled'],
    )
    page = browser.new_page()
    page.add_init_script(PROXY_JS)
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    # Check proxy is active
    proxy_check = page.evaluate("""() => {
        return {
            hasPX: !!window.PX,
            patched: window.PX?.__patched,
            hasPXProxy: !!window.__pxProxyActive
        };
    }""")
    print(f"[*] Proxy check: {proxy_check}", flush=True)
    
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
    except Exception as e:
        print(f"[-] No auth: {e}", flush=True)
    
    time.sleep(5)
    
    # Check setChallenge was intercepted
    check = page.evaluate("""() => {
        if (!window.PX || !window.PX.setChallenge) return 'no setChallenge';
        const src = window.PX.setChallenge.toString();
        return 'patched=' + (src.includes('_realSetChallenge') ? 'yes' : 'no');
    }""")
    print(f"[*] {check}", flush=True)
    
    # Check frames
    frames = page.frames
    arkose = [f for f in frames if 'arkose' in f.url]
    print(f"Frames: {len(frames)}, arkose: {len(arkose)}", flush=True)
    for f in frames:
        url = f.url[:120]
        if 'roblox' not in url:
            print(f"  {url}", flush=True)
    
    # Also check for console logs
    logs = page.evaluate("""() => {
        return window.__pxLogs || [];
    }""")
    print(f"Logs: {logs}", flush=True)
    
    page.screenshot(path="proxy_test.png")
    time.sleep(10)
    browser.close()
