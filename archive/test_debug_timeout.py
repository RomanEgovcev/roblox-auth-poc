"""Debug what's timing out during the challenge flow."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Monitor ALL requests and responses
    failed_reqs = []
    def on_request_failed(req):
        err = req.failure
        failed_reqs.append({"url": req.url, "error": err})
        print(f"[FAILED] {req.url}", flush=True)
        if err:
            print(f"  Error: {err}", flush=True)
    
    def on_response(resp):
        if "/v2/login" in resp.url or "proof-of-work" in resp.url or "challenge" in resp.url.lower():
            print(f"\n[RESP] {resp.status} {resp.url}", flush=True)
            for k, v in resp.headers.items():
                if k.lower() in ("content-type", "rblx-challenge-id", "rblx-challenge-type", "location"):
                    print(f"  {k}: {v}", flush=True)
    
    def on_request(req):
        if "pow-puzzle" in req.url or "challenge" in req.url.lower():
            print(f"[REQ] {req.method} {req.url}", flush=True)
    
    page.on("requestfailed", on_request_failed)
    page.on("response", on_response)
    page.on("request", on_request)
    page.on("pageerror", lambda err: print(f"[PAGE_ERROR] {err}", flush=True))
    page.on("console", lambda msg: print(f"[CONSOLE] {msg.text}", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    print("Page loaded", flush=True)
    
    # Fill credentials
    page.fill('input[name="username"]', "testuser123")
    page.fill('input[name="password"]', "TestPassword123!")
    time.sleep(1)
    
    # Trigger onFormSubmit
    page.evaluate("""() => {
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        if (!key) return;
        function walk(f, d) {
            if (!f || d > 20) return;
            if (f.memoizedProps && f.memoizedProps.onFormSubmit) {
                f.memoizedProps.onFormSubmit();
                return;
            }
            if (f.child) walk(f.child, d+1);
            if (f.sibling) walk(f.sibling, d);
        }
        walk(root[key], 0);
    }""")
    
    time.sleep(30)
    
    print(f"\n=== Summary ===", flush=True)
    for f in failed_reqs:
        print(f"FAILED: {f['url']}", flush=True)
    
    time.sleep(3)
    browser.close()
