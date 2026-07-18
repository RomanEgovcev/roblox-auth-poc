"""After challenge completes, click login again - PX should auto-include challenge headers."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page(bypass_csp=True)
    page.set_viewport_size({"width": 1280, "height": 900})
    
    login_attempts = 0
    challenge_id = None
    verify_done = False
    
    def on_resp(resp):
        global login_attempts, challenge_id, verify_done
        url = resp.url
        if "/v2/login" in url:
            login_attempts += 1
            print(f"[LOGIN {resp.status}] attempt#{login_attempts} {url}", flush=True)
            if resp.status == 403:
                challenge_id = resp.headers.get("rblx-challenge-id", "")
                print(f"  challenge_id={challenge_id[:30] if challenge_id else 'none'}...", flush=True)
        if "pow-puzzle" in url and resp.request.method == "POST" and "verify" not in url:
            try:
                import json
                body = resp.text()[:300]
                data = json.loads(body)
                if data.get("answerCorrect"):
                    verify_done = True
                    print(f"[VERIFIED] token={data.get('redemptionToken','')[:20]}...", flush=True)
            except: pass
    
    def on_console(msg):
        t = msg.text.lower()
        if any(x in t for x in ["worker", "challenge", "proof", "error", "exception", "fail"]):
            print(f"[CONSOLE] {msg.text[:200]}", flush=True)
    
    page.on("response", on_resp)
    page.on("console", on_console)
    page.on("pageerror", lambda e: print(f"[PAGE_ERR] {e}", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    print("Page loaded", flush=True)
    
    page.fill('input[name="username"]', 'testuser123')
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
    # First login attempt
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
    print("Login attempt #1", flush=True)
    
    # Wait for challenge to process
    time.sleep(30)
    print(f"Post-challenge cookies: {[c['name']+': '+c['value'][:30] for c in page.context.cookies()]}", flush=True)
    
    # Click login button again
    print("\n--- Attempt #2: clicking login button ---", flush=True)
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
    
    # Wait for result
    time.sleep(15)
    
    print(f"\n{'='*50}", flush=True)
    cookies = page.context.cookies()
    rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
    if rs:
        print(f"[SUCCESS] .ROBLOSECURITY={rs[0]['value'][:50]}...", flush=True)
        import httpx
        r = httpx.Client(cookies={".ROBLOSECURITY": rs[0]["value"]})
        auth = r.get("https://users.roblox.com/v1/users/authenticated")
        print(f"[AUTH CHECK] {auth.status_code} {auth.text[:200]}", flush=True)
    else:
        print(f"[NOPE] Total login attempts: {login_attempts}")
        print(f"[NOPE] Verify completed: {verify_done}")
        print(f"[NOPE] Page URL: {page.url}", flush=True)
        px3 = [c for c in cookies if c["name"] == "_px3"]
        if px3:
            print(f"[PX3] {px3[0]['value'][:50]}...", flush=True)
    print(f"{'='*50}", flush=True)
    
    browser.close()
