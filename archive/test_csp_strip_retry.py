"""Strip CSP + manual retry with redemption token from verify response."""
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
    login_success = False
    start = time.time()
    
    # Strip CSP from responses using route
    def route_handler(route):
        headers = route.request.headers
        route.continue_(headers={k:v for k,v in headers.items() if k.lower() != "content-security-policy"})
    
    def handle_response(resp):
        nonlocal redemption_token, challenge_id, csrf_token, retry_done, login_success
        
        url = resp.url
        method = resp.request.method
        
        if "/v2/login" in url:
            csrf = resp.headers.get("x-csrf-token", "")
            if csrf:
                csrf_token = csrf
                print(f"[CSRF] {csrf_token[:30]}...", flush=True)
            if resp.status == 403:
                challenge_id = resp.headers.get("rblx-challenge-id", "")
                print(f"[CHALLENGE] id={challenge_id[:30]}...", flush=True)
            
        if "pow-puzzle" in url and method == "POST":
            body = resp.text()[:500]
            print(f"[VERIFY] {resp.status} {body}", flush=True)
            try:
                data = json.loads(body)
                if data.get("answerCorrect") and data.get("redemptionToken"):
                    redemption_token = data["redemptionToken"]
                    print(f"[REDEMPTION] {redemption_token}", flush=True)
            except: pass
    
    page.on("response", handle_response)
    page.route("**/*", route_handler)
    
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
    
    # Wait and retry
    for i in range(0, 120, 5):
        time.sleep(5)
        elapsed = time.time() - start
        print(f"[{elapsed:.0f}s] waiting...", flush=True)
        
        if redemption_token and challenge_id and csrf_token and not retry_done:
            print(f"[RETRY] with token={redemption_token[:20]}...", flush=True)
            time.sleep(2)
            
            result = page.evaluate("""({token, csrf, challengeId}) => {
                return fetch('https://auth.roblox.com/v2/login?urlLocale=en_us', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json;charset=UTF-8',
                        'X-CSRF-TOKEN': csrf,
                        'rblx-challenge-id': challengeId,
                        'rblx-challenge-type': 'proofofwork',
                        'rblx-challenge-redemption-token': token
                    },
                    body: JSON.stringify({
                        ctype: 'username',
                        cvalue: 'testuser123',
                        password: 'TestPassword123!',
                        secureAuthIntent: true
                    }),
                    credentials: 'include'
                }).then(r => r.text().then(t => ({status: r.status, body: t})));
            }""", {"token": redemption_token, "csrf": csrf_token, "challengeId": challenge_id})
            print(f"[RETRY RESULT] status={result.get('status')} body={result.get('body','')[:300]}", flush=True)
            retry_done = True
            
            if result and result.get("status") == 200:
                login_success = True
                break
        
        cookies = page.context.cookies()
        if any(c["name"] == ".ROBLOSECURITY" for c in cookies):
            print("[SUCCESS] .ROBLOSECURITY cookie found!", flush=True)
            login_success = True
            break
    
    elapsed = time.time() - start
    print(f"\n{'='*50}", flush=True)
    print(f"TIME: {elapsed:.0f}s", flush=True)
    print(f"SUCCESS: {login_success}", flush=True)
    
    cookies = page.context.cookies()
    roblosecurity = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
    if roblosecurity:
        val = roblosecurity[0]["value"]
        print(f".ROBLOSECURITY: {val[:50]}...", flush=True)
        import httpx
        r = httpx.Client(cookies={".ROBLOSECURITY": val})
        auth = r.get("https://users.roblox.com/v1/users/authenticated")
        print(f"AUTH CHECK: {auth.status_code} {auth.text[:200]}", flush=True)
    else:
        print(f"Cookies: {[f'{c[\"name\"]}={c[\"value\"][:30]}' for c in cookies]}", flush=True)
    print(f"{'='*50}", flush=True)
    
    browser.close()
