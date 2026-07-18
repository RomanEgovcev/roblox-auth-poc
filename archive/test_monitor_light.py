"""Lightweight challenge monitor - events only, no route interception."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # EVENT-BASED monitoring only (no route interception)
    def on_req(req):
        url = req.url
        if any(x in url for x in ["/v2/login", "pow-puzzle", "worker", "verify"]):
            print(f"[REQ] {req.method} {url}", flush=True)
    
    def on_resp(resp):
        url = resp.url
        if any(x in url for x in ["/v2/login", "pow-puzzle", "worker", "verify"]):
            print(f"[RESP {resp.status}] {url}", flush=True)
            if "pow-puzzle" in url and resp.status == 200 and "verify" not in url:
                body = resp.text()[:500]
                print(f"[PUZZLE BODY] {body}", flush=True)
    
    def on_req_fail(req):
        url = req.url
        if any(x in url for x in ["pow", "worker", "challenge", "verify"]):
            print(f"[FAILED] {req.method} {url}: {req.failure}", flush=True)
    
    def on_console(msg):
        text = msg.text
        if any(x in text.lower() for x in ["worker", "challenge", "proof", "pow", "dialog", "modal"]):
            print(f"[CONSOLE] {text[:250]}", flush=True)
    
    page.on("request", on_req)
    page.on("response", on_resp)
    page.on("requestfailed", on_req_fail)
    page.on("console", on_console)
    page.on("pageerror", lambda err: print(f"[PAGE_ERROR] {err}", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    print("Page loaded", flush=True)
    
    # Fill credentials
    page.fill('input[name="username"]', 'testuser123')
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
    # Trigger login
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
    print("Login triggered", flush=True)
    
    # Wait up to 3 minutes
    max_wait = 180
    start = time.time()
    success = False
    cookies = None
    
    for i in range(0, max_wait, 10):
        time.sleep(min(10, max_wait - i))
        elapsed = time.time() - start
        print(f"  Waiting... ({elapsed:.0f}s)", flush=True)
        
        cur_url = page.url
        if "home" in cur_url.lower() or "games" in cur_url.lower():
            print(f"[REDIRECT] URL changed to: {cur_url}", flush=True)
            cookies = page.context.cookies()
            roblosecurity = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
            if roblosecurity:
                print(f"[SUCCESS] Got .ROBLOSECURITY!", flush=True)
                success = True
                break
        
        # Also check cookies directly
        cookies = page.context.cookies()
        roblosecurity = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
        if roblosecurity and not success:
            print(f"[SUCCESS] .ROBLOSECURITY cookie found on login page!", flush=True)
            success = True
            break
    
    elapsed = time.time() - start
    print(f"\n{'='*50}", flush=True)
    print(f"WAIT TIME: {elapsed:.0f}s", flush=True)
    print(f"SUCCESS: {success}", flush=True)
    print(f"FINAL URL: {page.url}", flush=True)
    
    if success and roblosecurity:
        cookie_val = roblosecurity[0]["value"]
        print(f".ROBLOSECURITY: {cookie_val[:50]}...", flush=True)
        
        # Verify with an authenticated endpoint
        import httpx
        h = httpx.Client(cookies={".ROBLOSECURITY": cookie_val})
        r = h.get("https://users.roblox.com/v1/users/authenticated")
        print(f"AUTH VERIFY: {r.status_code} {r.text[:200]}", flush=True)
    else:
        cookies = page.context.cookies()
        print(f"All cookies:", flush=True)
        for c in cookies:
            print(f"  {c['name']}={c['value'][:40]}...", flush=True)
    
    print(f"{'='*50}", flush=True)
    browser.close()
