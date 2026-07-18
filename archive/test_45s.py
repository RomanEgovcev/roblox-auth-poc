"""No route - just wait 45s to confirm login POST happens."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    t0 = [None]
    saw_login = [False]
    
    def on_req(req):
        if t0[0] is not None and "/v2/login" in req.url and req.method == "POST":
            saw_login[0] = True
            print(f"LOGIN POST at {time.time()-t0[0]:.0f}s", flush=True)
    page.on("request", on_req)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    page.evaluate("""() => {
        for (let i = 0; i < 30; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 100+i*20, clientY: 200+i*5, bubbles: true}));
        document.querySelector('input[name="username"]')?.focus();
    }""")
    time.sleep(1)
    page.fill('input[name="username"]', 'testuser123')
    time.sleep(0.5)
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    page.evaluate("""() => {
        for (let i = 0; i < 15; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 500+i*20, clientY: 300+i*5, bubbles: true}));
    }""")
    time.sleep(0.5)
    
    t0[0] = time.time()
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
    print(f"[t=0] Submitted", flush=True)
    
    for i in range(45):
        time.sleep(1)
        if saw_login[0]:
            print(f"Login happened at t={i+1}s, now waiting for challenge to complete...", flush=True)
            time.sleep(20)
            break
        if i % 5 == 4:
            print(f"[t={i+1}] no login yet...", flush=True)
    
    print(f"\nResult: login={saw_login[0]}", flush=True)
    browser.close()
