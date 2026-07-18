"""Detailed tracing: what happens after 403 in the browser."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page(bypass_csp=True)
    page.set_viewport_size({"width": 1280, "height": 900})
    
    def on_req(req):
        url = req.url
        if any(x in url for x in ["/v2/login", "pow-puzzle", "challenge", "worker", "main.min"]):
            print(f"[REQ {time.time():.1f}] {req.method} {url}", flush=True)
        if "pow-puzzle" in url:
            import re
            m = re.search(r'sessionID=([^&]+)', url)
            if m:
                print(f"  SESSION: {m.group(1)}", flush=True)
    
    def on_resp(resp):
        url = resp.url
        if any(x in url for x in ["/v2/login", "pow-puzzle", "challenge", "worker"]):
            print(f"[RES {time.time():.1f}] {resp.status} {resp.request.method} {url}", flush=True)
            if "pow-puzzle" in url and resp.request.method == "POST":
                try:
                    print(f"  BODY: {resp.text()[:300]}", flush=True)
                except:
                    pass
    
    def on_console(msg):
        t = msg.text.lower()
        if any(x in t for x in ["worker", "challenge", "proof", "pow", "error", "eval", "fail"]):
            print(f"[CONSOLE {time.time():.1f}] [{msg.type}] {msg.text[:250]}", flush=True)
    
    page.on("request", on_req)
    page.on("response", on_resp)
    page.on("console", on_console)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    print("--- Page loaded, filling form ---", flush=True)
    
    page.fill('input[name="username"]', 'testuser123')
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
    print("--- Triggering login ---", flush=True)
    page.evaluate("""() => {
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        if (!key) return;
        function walk(f, d) {
            if (!f || d > 20) return;
            if (f.memoizedProps && typeof f.memoizedProps.onFormSubmit === 'function') {
                f.memoizedProps.onFormSubmit();
                return;
            }
            if (f.child) walk(f.child, d+1);
            if (f.sibling) walk(f.sibling, d);
        }
        walk(root[key], 0);
    }""")
    print("--- Login triggered, waiting 30s ---", flush=True)
    
    time.sleep(30)
    
    print("\n=== SUMMARY ===", flush=True)
    cookies = page.context.cookies()
    has_cf = any(c["name"] == "__cf_bm" for c in cookies)
    has_rs = any(c["name"] == ".ROBLOSECURITY" for c in cookies)
    print(f"ROBLOSECURITY={has_rs} CF={has_cf}", flush=True)
    
    browser.close()
