"""Simplified: flow with route intercept to modify continue response."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    events = []  # (time, msg)
    
    def log(msg):
        events.append((time.time(), msg))
    
    def on_req(req):
        if any(x in req.url for x in ("/v2/login", "pow-puzzle", "challenge/v1", "px-cloud", "worker-resources")):
            log(f"REQ {req.method} {req.url[:120]}")
    page.on("request", on_req)
    
    def on_resp_capture(resp):
        if any(x in resp.url for x in ("/v2/login", "pow-puzzle", "challenge/v1/continue")):
            try:
                body = resp.body()[:500]
                log(f"RESP {resp.status} {resp.url[:90]} body={body[:200]}")
            except Exception as e:
                log(f"RESP {resp.status} {resp.url[:90]} body_err={e}")
    page.on("response", on_resp_capture)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    # Mouse interaction
    page.evaluate("""() => {
        for (let i = 0; i < 30; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 100+i*20, clientY: 200+i*5, bubbles: true}));
        document.querySelector('input[name="username"]')?.focus();
    }""")
    time.sleep(0.3)
    page.fill('input[name="username"]', 'testuser123')
    time.sleep(0.3)
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(0.3)
    page.evaluate("""() => {
        for (let i = 0; i < 15; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 400+i*15, clientY: 350+i*3, bubbles: true}));
    }""")
    time.sleep(0.3)
    
    t0 = time.time()
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
    log("SUBMITTED")
    
    time.sleep(20)
    
    print("=== Timeline ===", flush=True)
    events.sort(key=lambda x: x[0])
    for ts, msg in events:
        print(f"[{ts-t0:6.2f}s] {msg}", flush=True)
    
    cookies = ctx.cookies()
    rs = [c for c in cookies if ".ROBLOSECURITY" in c["name"]]
    print(f"\nROBLOSECURITY: {len(rs)}", flush=True)
    if rs:
        print(f"Cookie: {rs[0]['value'][:50]}...", flush=True)
    
    browser.close()
