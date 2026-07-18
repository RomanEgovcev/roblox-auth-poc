"""Log ALL requests during the delay period."""
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
        if dt > 3 and req.method == "GET" and "rcdn" in req.url:
            return  # skip CSS/JS asset loads after t=3
        print(f"[{dt:5.1f}s] {req.method} {req.url[:120]}", flush=True)
    
    page.on("request", on_req)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    page.fill('input[name="username"]', 'testuser123')
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
    page.evaluate("""() => {
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        function walk(f, d) {
            if (!f || d > 20) return null;
            if (f.memoizedProps && typeof f.memoizedProps.onFormSubmit === 'function') {
                f.memoizedProps.onFormSubmit();
                return 'ok';
            }
            return walk(f.child, d+1) || walk(f.sibling, d);
        }
        return walk(root[key], 0);
    }""")
    t0[0] = time.time()
    print(f"[t=0] fired onFormSubmit", flush=True)
    
    time.sleep(50)
    print(f"\n[t=50] done", flush=True)
    browser.close()
