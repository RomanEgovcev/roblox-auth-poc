"""Fiber walker with request monitoring."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    t0 = [None]
    
    def on_req(req):
        if t0[0] is None:
            return
        dt = time.time() - t0[0]
        url = req.url
        if any(x in url for x in ("/v2/login", "pow-puzzle", "challenge/v1", "px-cloud", "main.min.js")):
            print(f"[{dt:5.1f}s] {req.method} {url[:140]}", flush=True)
        if "/v2/login" in url and req.method == "POST":
            print(f"[LOGIN POST at {dt:.1f}s]", flush=True)
    
    page.on("request", on_req)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    print("Page loaded", flush=True)
    time.sleep(5)
    
    page.fill('input[name="username"]', 'testuser123')
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
    result = page.evaluate("""() => {
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        if (!key) { console.log('NO_FIBER_KEY'); return 'no_fiber_key'; }
        function walk(f, d) {
            if (!f || d > 20) return null;
            if (f.memoizedProps && typeof f.memoizedProps.onFormSubmit === 'function') {
                console.log('FOUND_onFormSubmit at depth', d);
                f.memoizedProps.onFormSubmit();
                return 'onFormSubmit called at depth ' + d;
            }
            return walk(f.child, d+1) || walk(f.sibling, d);
        }
        return walk(root[key], 0);
    }""")
    t0[0] = time.time()
    print(f"[t=0] Fiber walker result: {result}", flush=True)
    
    time.sleep(60)
    print(f"[t=60] Done waiting", flush=True)
    browser.close()
