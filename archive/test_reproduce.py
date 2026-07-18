"""Reproduce successful flow from test_humanlike.py with timing."""
import os, time, json
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
        if any(x in req.url for x in ("/v2/login", "pow-puzzle", "challenge/v1", "px-cloud", "worker-resources", "account-security")):
            marker = " ** LOGIN **" if "/v2/login" in req.url else ""
            print(f"[{dt:6.2f}s] {req.method} {req.url[:120]}{marker}", flush=True)
    page.on("request", on_req)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    # Mouse interaction (matching test_humanlike.py timing)
    page.evaluate("""() => {
        for (let i = 0; i < 20; i++) {
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 100 + i * 30, clientY: 200 + i * 10, bubbles: true}));
        }
        const u = document.querySelector('input[name="username"]');
        if (u) { u.focus(); u.dispatchEvent(new Event('focus', {bubbles: true})); }
    }""")
    time.sleep(1)
    page.fill('input[name="username"]', 'testuser123')
    time.sleep(0.5)
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    page.evaluate("""() => {
        for (let i = 0; i < 10; i++) {
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 500 + i * 20, clientY: 300 + i * 5, bubbles: true}));
        }
    }""")
    time.sleep(1)
    
    t0[0] = time.time()
    page.evaluate("""() => {
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        function walk(f, d) {
            if (!f || d > 20) return null;
            if (f.memoizedProps && typeof f.memoizedProps.onFormSubmit === 'function') {
                f.memoizedProps.onFormSubmit();
                return 'ok depth ' + d;
            }
            return walk(f.child, d+1) || walk(f.sibling, d);
        }
        return walk(root[key], 0);
    }""")
    print(f"[t=0] Submitted", flush=True)
    
    time.sleep(15)
    print(f"Done in {time.time()-t0[0]:.0f}s", flush=True)
    browser.close()
