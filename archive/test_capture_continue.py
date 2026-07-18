"""Intercept /challenge/v1/continue at route level AND monitor challenge progress."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page(bypass_csp=True)
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Track verification by intercepting all pow-puzzle POSTs
    verify_done = [False]
    continue_body = [None]
    
    def on_req(req):
        url = req.url
        method = req.method
        if "/challenge/v1/continue" in url and method == "POST":
            try:
                body = req.post_data
                continue_body[0] = body
                print(f"\n[CONTINUE REQUEST BODY] {body}\n", flush=True)
            except Exception as e:
                print(f"[CONTINUE REQ ERR] {e}", flush=True)
        if "pow-puzzle" in url:
            if method == "POST":
                verify_done[0] = True
                print(f"[VERIFY POST] {url}", flush=True)
            elif method == "GET":
                # Extract session ID
                import re
                m = re.search(r'sessionID=([^&]+)', url)
                if m:
                    print(f"[PUZZLE SESSION] {m.group(1)}", flush=True)
    
    def on_console(msg):
        t = msg.text.lower()
        if any(x in t for x in ["worker", "challenge", "proof", "pow", "error", "eval", "verify", "answer", "correct"]):
            print(f"[CONSOLE] {msg.text[:300]}", flush=True)
        # Always print errors
        if msg.type == "error":
            print(f"[CONSOLE ERROR] {msg.text[:300]}", flush=True)
    
    page.on("request", on_req)
    page.on("console", on_console)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    
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
    
    start = time.time()
    while time.time() - start < 30:
        time.sleep(1)
        if verify_done[0] and continue_body[0]:
            print(f"\nBOTH verify and continue captured!", flush=True)
            break
    
    elapsed = time.time() - start
    print(f"\n{'='*50}", flush=True)
    print(f"TIME: {elapsed:.0f}s verify={verify_done[0]} continue={continue_body[0] is not None}", flush=True)
    
    if continue_body[0]:
        try:
            parsed = json.loads(continue_body[0])
            print(f"CONTINUE BODY (parsed): {json.dumps(parsed, indent=2)}", flush=True)
        except:
            print(f"CONTINUE BODY (raw): {continue_body[0]}", flush=True)
    
    cookies = page.context.cookies()
    has_rs = any(c["name"] == ".ROBLOSECURITY" for c in cookies)
    has_cf = any(c["name"] == "__cf_bm" for c in cookies)
    print(f"RS={has_rs} CF={has_cf}", flush=True)
    print(f"{'='*50}", flush=True)
    
    browser.close()
