"""Test: does ANY page.route break the challenge flow?"""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    t0 = [None]
    
    # Register route for nonexistent URL
    def dummy_handler(route, request):
        if "/nonexistent/" in request.url:
            print(f"[DUMMY ROUTE] {request.url}", flush=True)
        route.continue_()
    page.route("**/nonexistent/**", dummy_handler)
    
    def on_req(req):
        if t0[0] is not None and any(x in req.url for x in ("/v2/login", "pow-puzzle", "challenge/v1", "worker-resources")):
            dt = time.time() - t0[0]
            m = " **LOGIN**" if "/v2/login" in req.url else ""
            print(f"[{dt:5.1f}s] REQ {req.method} {req.url[:110]}{m}", flush=True)
    
    def on_resp(resp):
        if t0[0] is not None and any(x in resp.url for x in ("/v2/login", "/challenge/v1/continue")):
            dt = time.time() - t0[0]
            try:
                b = resp.body()[:200]
                print(f"[{dt:5.1f}s] RESP {resp.status} {resp.url[:80]} {b}", flush=True)
            except:
                print(f"[{dt:5.1f}s] RESP {resp.status} {resp.url[:80]}", flush=True)
    
    page.on("request", on_req)
    page.on("response", on_resp)
    
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
    
    for i in range(15):
        time.sleep(1)
        if i % 5 == 4:
            print(f"[t={i+1}] waiting...", flush=True)
    
    print(f"\nDone", flush=True)
    browser.close()
