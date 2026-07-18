"""
React login flow - wait long enough for PX to solve challenge and retry.
"""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    login_success = False
    login_retry = None
    
    def on_response(resp):
        global login_success, login_retry
        if "/v2/login" in resp.url:
            if resp.status == 200:
                login_success = True
                print(f"\n*** LOGIN SUCCESS! ***", flush=True)
            elif resp.status == 403:
                h = resp.headers
                if "rblx-challenge-redemption-token" in str(dict(h)):
                    print(f"[RETRY] 403 with redemption token (still challenged)", flush=True)
                elif "rblx-challenge-id" in h:
                    print(f"[CHALLENGE] 403 - challenge issued", flush=True)
            login_retry = {"status": resp.status, "headers": dict(resp.headers)}
            print(f"[RESP] {resp.status} {resp.url}", flush=True)
    
    def on_request(req):
        if "/v2/login" in req.url and req.method == "POST":
            h = dict(req.headers)
            has_challenge = "rblx-challenge-redemption-token" in h
            print(f"[REQ] POST /v2/login (challenge_headers={has_challenge})", flush=True)
            if has_challenge:
                print(f"  challenge-id: {h.get('rblx-challenge-id', '')}", flush=True)
                print(f"  redemption: {h.get('rblx-challenge-redemption-token', '')[:20]}...", flush=True)
    
    page.on("response", on_response)
    page.on("request", on_request)
    page.on("console", lambda msg: print(f"[CONSOLE] {msg.text[:200]}", flush=True))
    
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
    
    # Wait for challenge to complete (computation ~3s + retry)
    print("\nWaiting for PX challenge to complete...", flush=True)
    for i in range(90):  # 90 seconds
        time.sleep(1)
        if login_success:
            print(f"\n*** LOGIN SUCCESS DETECTED at second {i+1}! ***", flush=True)
            break
        if i % 10 == 9:
            print(f"  Still waiting ({i+1}s)...", flush=True)
    
    print(f"\nFinal URL: {page.url}", flush=True)
    print(f"Login success: {login_success}", flush=True)
    if login_retry:
        print(f"Last login response: {login_retry['status']}", flush=True)
    
    time.sleep(5)
    browser.close()
