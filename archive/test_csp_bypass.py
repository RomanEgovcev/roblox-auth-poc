"""Test with CSP bypass to fix WebWorker creation."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # CRITICAL: bypass_csp allows WebWorker from blob URLs
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page(bypass_csp=True)  # This strips CSP enforcement
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Lightweight monitoring
    def on_resp(resp):
        url = resp.url
        if any(x in url for x in ["/v2/login", "pow-puzzle", "worker-resources", "verify"]):
            print(f"[RESP {resp.status}] {resp.request.method} {url}", flush=True)
        if "pow-puzzle" in url and resp.request.method == "POST":
            print(f"[VERIFY BODY] {resp.text()[:300]}", flush=True)
    
    def on_console(msg):
        t = msg.text.lower()
        if any(x in t for x in ["worker", "challenge", "proof", "pow", "dialog", "fail", "error"]):
            print(f"[CONSOLE] {msg.text[:250]}", flush=True)
    
    page.on("response", on_resp)
    page.on("console", on_console)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    print("Page loaded", flush=True)
    
    page.fill('input[name="username"]', 'testuser123')
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
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
    
    # Wait up to 120 seconds for challenge to complete
    start = time.time()
    success = False
    for i in range(0, 120, 5):
        time.sleep(5)
        print(f"  [{time.time()-start:.0f}s] waiting...", flush=True)
        
        # Check for success
        cookies = page.context.cookies()
        rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
        if rs:
            print(f"\n[SUCCESS!] .ROBLOSECURITY={rs[0]['value'][:50]}...", flush=True)
            success = True
            break
        
        # Check URL
        cur_url = page.url
        if "home" in cur_url.lower() or "games" in cur_url.lower():
            print(f"[REDIRECT] URL={cur_url}", flush=True)
    
    elapsed = time.time() - start
    print(f"\n{'='*50}", flush=True)
    print(f"TIME: {elapsed:.0f}s SUCCESS: {success}", flush=True)
    if not success:
        cookies = page.context.cookies()
        names = [c["name"] + "=" + c["value"][:20] for c in cookies]
        print(f"Cookies: {names}", flush=True)
    print(f"{'='*50}", flush=True)
    
    browser.close()
