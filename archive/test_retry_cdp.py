"""Intercept verify response, then handle retry at CDP level."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    redemption_token = None
    challenge_id = None
    csrf_token = None
    retry_done = False
    start = time.time()
    
    def handle_response(resp):
        nonlocal redemption_token, challenge_id, csrf_token
        url = resp.url
        if "/v2/login" in url:
            if resp.status == 403:
                challenge_id = resp.headers.get("rblx-challenge-id", "")
                print(f"[403] challenge_id={challenge_id[:30]}...", flush=True)
            csrf = resp.headers.get("x-csrf-token", "")
            if csrf:
                csrf_token = csrf
                print(f"[CSRF] {csrf[:30]}...", flush=True)
        if "pow-puzzle" in url and resp.request.method == "POST":
            body = resp.text()[:500]
            print(f"[VERIFY] {body}", flush=True)
            try:
                d = json.loads(body)
                if d.get("answerCorrect") and d.get("redemptionToken"):
                    redemption_token = d["redemptionToken"]
                    print(f"[TOKEN] {redemption_token}", flush=True)
            except: pass
    
    page.on("response", handle_response)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
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
    
    # Wait for verify response, then retry at CDP level
    verified_time = None
    for i in range(0, 60, 2):
        time.sleep(2)
        if redemption_token and not retry_done:
            verified_time = time.time()
            print(f"\n[MANUAL RETRY via page.route]", flush=True)
            
            # Use page.route to intercept and retry at CDP level
            # This bypasses PX's JS interceptor entirely
            retry_data = {
                "ctype": "username",
                "cvalue": "testuser123",
                "password": "TestPassword123!",
                "secureAuthIntent": True
            }
            
            # Set up route handler for the retry
            retry_result = [None]
            def retry_handler(route):
                retry_result[0] = {"url": route.request.url, "method": route.request.method}
                route.continue_()
            
            page.route("**/v2/login", retry_handler)
            
            # Make the retry request from page context with proper headers
            result = page.evaluate("""({token, csrf, challengeId, body}) => {
                return fetch('https://auth.roblox.com/v2/login?urlLocale=en_us', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json;charset=UTF-8',
                        'X-CSRF-TOKEN': csrf,
                        'rblx-challenge-id': challengeId,
                        'rblx-challenge-type': 'proofofwork',
                        'rblx-challenge-redemption-token': token
                    },
                    body: JSON.stringify(body),
                    credentials: 'include'
                }).then(r => r.text().then(t => ({
                    status: r.status,
                    body: t,
                    headers: Object.fromEntries(r.headers.entries())
                }))).catch(e => ({error: e.message}));
            }""", {"token": redemption_token, "csrf": csrf_token, "challengeId": challenge_id, "body": retry_data})
            
            print(f"[RETRY] {result}", flush=True)
            retry_done = True
            
            page.unroute("**/v2/login")
            
            if result and isinstance(result, dict) and result.get("status") == 200:
                break
        
        # Check for direct success
        cookies = page.context.cookies()
        if any(c["name"] == ".ROBLOSECURITY" for c in cookies):
            print("[SUCCESS] .ROBLOSECURITY found!", flush=True)
            break
    
    print(f"\n{'='*50}", flush=True)
    elapsed = time.time() - start
    print(f"TIME: {elapsed:.0f}s", flush=True)
    
    cookies = page.context.cookies()
    rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
    if rs:
        print(f"SUCCESS: {rs[0]['value'][:50]}...", flush=True)
        import httpx
        r = httpx.Client(cookies={".ROBLOSECURITY": rs[0]["value"]})
        auth = r.get("https://users.roblox.com/v1/users/authenticated")
        print(f"AUTH: {auth.status_code} {auth.text[:200]}", flush=True)
    else:
        print(f"FAILED - {[f'{c[\"name\"]}' for c in cookies]}", flush=True)
    print(f"{'='*50}", flush=True)
    
    browser.close()
