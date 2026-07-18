"""Comprehensive challenge flow monitor - captures everything, no monkey-patches."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

events = []
def log(what, extra=""):
    t = time.time()
    events.append((t, what, extra))
    print(f"[{t:.0f}] {what}{extra}", flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})

    # Route-based monitoring (captures ABSOLUTELY everything)
    challenges = {"login_req": None, "puzzle_resp": None, "verify_req": None, "retry_req": None}
    
    def route_handler(route):
        url = route.request.url
        method = route.request.method
        is_v2_login = "/v2/login" in url
        is_puzzle = "pow-puzzle" in url
        is_worker = "worker-resources" in url or "ChallengeWebWorkers" in url
        
        if is_v2_login or is_puzzle or is_worker:
            log("REQ", f" {method} {url}")
        
        route.continue_()
    
    def handle_response(resp):
        url = resp.url
        if "/v2/login" in url:
            body = resp.text()[:500] if resp.status >= 400 else ""
            log("RESP", f" {resp.status} {url} body={body[:200]}")
            if resp.status == 403 and not challenges["login_req"]:
                challenges["login_req"] = {"url": url, "headers": dict(resp.headers)}
            elif resp.status == 200:
                challenges["login_success"] = {"url": url, "headers": dict(resp.headers)}
                log("SUCCESS!", f" Login succeeded!")
        elif "pow-puzzle" in url and resp.status == 200:
            body = resp.text()[:300]
            challenges["puzzle_resp"] = {"url": url, "body": body}
            log("PUZZLE", f" 200 - body={body}")
        elif "pow-puzzle" in url and "verify" in url:
            challenges["verify_req"] = {"url": url, "status": resp.status}
            log("VERIFY", f" {resp.status} {url}")
        elif "worker-resources" in url or "ChallengeWebWorkers" in url:
            log("WORKER_SCRIPT", f" {resp.status} {url}")
    
    page.on("response", handle_response)
    page.route("**/*", route_handler)
    
    # Console monitoring
    page.on("console", lambda msg: log("CONSOLE", f" {msg.type}: {msg.text[:200]}") if "challenge" in msg.text.lower() or "worker" in msg.text.lower() or "pow" in msg.text.lower() or "proof" in msg.text.lower() or msg.type == "error" else None)
    page.on("pageerror", lambda err: log("PAGE_ERROR", f" {err}"))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    log("PAGE_LOADED")
    
    # Fill credentials
    page.fill('input[name="username"]', 'testuser123')
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
    # Trigger login via React fiber
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
    
    # Wait up to 5 minutes, checking for completion every 10s
    start = time.time()
    max_wait = 300
    for i in range(0, max_wait, 10):
        time.sleep(min(10, max_wait - i))
        if i % 60 == 0 and i > 0:
            log(f"WAIT {i}s")
        if challenges.get("login_success"):
            log("LOGIN_SUCCESS_DETECTED!")
            break
        # Check if we're still on login page
        if i > 10 and i % 30 == 0:
            cur_url = page.url
            log("URL", f" {cur_url}")
            if "home" in cur_url:
                log("REDIRECTED_TO_HOME!")
                challenges["login_success"] = True
                break
    
    elapsed = time.time() - start
    log(f"DONE after {elapsed:.0f}s")
    
    # Print summary
    cookies = page.context.cookies()
    roblosecurity = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
    print(f"\n=== SUMMARY ===", flush=True)
    print(f"Login success: {bool(challenges.get('login_success'))}", flush=True)
    print(f".ROBLOSECURITY found: {len(roblosecurity)}", flush=True)
    if roblosecurity:
        print(f".ROBLOSECURITY value: {roblosecurity[0]['value'][:30]}...", flush=True)
    print(f"All logon challenge events:", flush=True)
    for t, what, extra in events:
        if any(k in str(what) for k in ["REQ", "RESP", "PUZZLE", "VERIFY", "WORKER", "SUCCESS", "URL"]):
            print(f"  [{t-start:.0f}s] {what}{extra}", flush=True)
    
    input("Press Enter to close...")
    browser.close()
