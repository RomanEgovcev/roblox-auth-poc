"""Intercept /challenge/v1/continue to bypass captcha."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    # Intercept /challenge/v1/continue to modify response
    def handle_continue(route, request):
        if "/challenge/v1/continue" in request.url:
            print(f"[INTERCEPT] /challenge/v1/continue {request.post_data[:100]}", flush=True)
            route.continue_()
        else:
            route.continue_()
    
    page.route("**/challenge/v1/continue**", handle_continue)
    
    # Monitor login responses
    login_responses = []
    def on_resp(resp):
        if "/v2/login" in resp.url:
            login_responses.append((resp.status, resp.url))
            print(f"[LOGIN RESP] {resp.status}", flush=True)
    page.on("response", on_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    # Mouse interaction
    page.evaluate("""() => {
        for (let i = 0; i < 30; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 100+i*20, clientY: 200+i*5, bubbles: true}));
        const u = document.querySelector('input[name="username"]');
        if (u) { u.focus(); u.dispatchEvent(new FocusEvent('focus', {bubbles: true})); }
    }""")
    time.sleep(0.5)
    page.fill('input[name="username"]', 'testuser123')
    time.sleep(0.3)
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(0.5)
    page.evaluate("""() => {
        for (let i = 0; i < 15; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 400+i*15, clientY: 350+i*3, bubbles: true}));
    }""")
    time.sleep(0.3)
    
    t0 = time.time()
    print(f"[t=0] Submitting...", flush=True)
    
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
    
    time.sleep(20)
    
    print(f"\nLogin responses: {login_responses}", flush=True)
    cookies = ctx.cookies()
    rs = [c for c in cookies if ".ROBLOSECURITY" in c["name"]]
    print(f"ROBLOSECURITY: {len(rs)}", flush=True)
    if rs:
        print(f"Cookie: {rs[0]['value'][:50]}...", flush=True)
    
    print(f"Done in {time.time()-t0:.0f}s", flush=True)
    browser.close()
