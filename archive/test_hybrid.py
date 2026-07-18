"""Hybrid approach: browser handles puzzle, CDP intercepts + retries login."""
import os, time, json, re
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
import httpx

login_data = {
    "body": None,
    "csrf": None,
    "challenge_id": None,
    "challenge_type": None,
    "puzzle_session": None,
    "redemption_token": None,
    "retried": False,
}

def _fulfill(route, resp):
    hdrs = {}
    for name, value in resp.headers.items():
        lname = name.lower()
        if lname in ("transfer-encoding", "content-encoding", "content-security-policy"):
            continue
        if lname == "set-cookie":
            if "set-cookie" in hdrs:
                hdrs["set-cookie"] += f", {value}"
            else:
                hdrs["set-cookie"] = value
        else:
            hdrs[name] = value
    hdrs["Content-Length"] = str(len(resp.content))
    route.fulfill(status=resp.status_code, headers=hdrs, body=resp.content)

def handle_login(route, request):
    if login_data["retried"]:
        route.continue_()
        return
    
    body_str = request.post_data or "{}"
    body_data = json.loads(body_str)
    csrf = dict(request.headers).get("x-csrf-token", "")
    
    if login_data["body"] is None:
        # First attempt - block and handle via httpx
        login_data["body"] = body_data
        login_data["csrf"] = csrf
        _do_first_login(route, request)
    else:
        # Second attempt (retry) - let it through if challenge headers present
        req_headers = dict(request.headers)
        if "rblx-challenge-id" in req_headers:
            print("\n[HANDLER] Retry detected - letting through!\n", flush=True)
            login_data["retried"] = True
            route.continue_()
        else:
            route.continue_()

def _do_first_login(route, request):
    ctx = request.frame.page.context
    browser_cookies = {c["name"]: c["value"] for c in ctx.cookies()}
    h = httpx.Client(cookies=browser_cookies, verify=True, timeout=60)
    
    login_url = "https://auth.roblox.com/v2/login?urlLocale=en_us"
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://www.roblox.com",
        "X-CSRF-TOKEN": login_data["csrf"],
    }
    
    r1 = h.post(login_url, json=login_data["body"], headers=hdrs, follow_redirects=False)
    print(f"[HANDLER] 1st login: {r1.status_code}", flush=True)
    
    if r1.status_code != 403 or "rblx-challenge-id" not in r1.headers:
        print("[HANDLER] No challenge", flush=True)
        _fulfill(route, r1)
        return
    
    login_data["challenge_id"] = r1.headers.get("rblx-challenge-id", "")
    login_data["challenge_type"] = r1.headers.get("rblx-challenge-type", "")
    login_data["csrf"] = r1.headers.get("x-csrf-token", login_data["csrf"])
    
    print(f"[HANDLER] Challenge: {login_data['challenge_id']}", flush=True)
    
    # Fulfill with the 403 so browser's PX handles the challenge
    _fulfill(route, r1)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Track puzzle and verify
    def on_req(req):
        url = req.url
        if "pow-puzzle" in url and "sessionID" in url:
            m = re.search(r'sessionID=([^&]+)', url)
            if m:
                login_data["puzzle_session"] = m.group(1)
                print(f"[PUZZLE SESSION] {login_data['puzzle_session']}", flush=True)
        if "pow-puzzle" in url and req.method == "POST":
            print(f"[VERIFY POST]", flush=True)
    
    def on_resp(resp):
        url = resp.url
        if "pow-puzzle" in url and resp.request.method == "POST":
            try:
                body = resp.text()[:300]
                print(f"[VERIFY RESP] {body}", flush=True)
                result = json.loads(resp.text())
                if result.get("answerCorrect") and result.get("redemptionToken"):
                    login_data["redemption_token"] = result["redemptionToken"]
                    print(f"[TOKEN] {login_data['redemption_token'][:30]}...", flush=True)
            except Exception as e:
                print(f"[VERIFY ERR] {e}", flush=True)
    
    page.on("request", on_req)
    page.on("response", on_resp)
    page.route("**/v2/login*", handle_login)
    
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
    
    # Wait for challenge to complete in browser (up to 45s)
    start = time.time()
    while time.time() - start < 45:
        time.sleep(1)
        
        if login_data["redemption_token"] and not login_data["retried"]:
            print(f"\n[RETRYING] token={login_data['redemption_token'][:30]}...", flush=True)
            
            # Get cookies NOW (after puzzle solved - _px3 may be updated)
            browser_cookies = {c["name"]: c["value"] for c in ctx.cookies()}
            h = httpx.Client(cookies=browser_cookies, verify=True, timeout=60)
            
            login_url = "https://auth.roblox.com/v2/login?urlLocale=en_us"
            hdrs = {
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/json;charset=UTF-8",
                "Origin": "https://www.roblox.com",
                "X-CSRF-TOKEN": login_data["csrf"],
            }
            
            # Step A: Try /challenge/v1/continue first
            continue_url = "https://apis.roblox.com/challenge/v1/continue?urlLocale=en_us"
            continue_body = {
                "challengeId": login_data["challenge_id"],
                "redemptionToken": login_data["redemption_token"],
                "challengeType": login_data["challenge_type"],
            }
            r4 = h.post(continue_url, json=continue_body, headers=hdrs, timeout=30)
            print(f"[CONTINUE] {r4.status_code} {r4.text[:150]}", flush=True)
            
            # Step B: Retry login with challenge headers
            retry_hdrs = {
                **hdrs,
                "rblx-challenge-id": login_data["challenge_id"],
                "rblx-challenge-type": login_data["challenge_type"],
                "rblx-challenge-redemption-token": login_data["redemption_token"],
                "X-CSRF-TOKEN": login_data["csrf"],
            }
            r5 = h.post(login_url, json=login_data["body"], headers=retry_hdrs, follow_redirects=False)
            print(f"[RETRY] {r5.status_code} {r5.text[:300]}", flush=True)
            
            if r5.status_code == 200:
                print("[SUCCESS!]", flush=True)
                # Check for .ROBLOSECURITY
                set_cookie = r5.headers.get("set-cookie", "")
                if ".ROBLOSECURITY" in set_cookie:
                    print(f"[ROBLOSECURITY] {set_cookie[:100]}...", flush=True)
            
            break
        
        # Check if page navigated away (login success)
        cur_url = page.url
        if "home" in cur_url or "games" in cur_url:
            print(f"[REDIRECT] {cur_url}", flush=True)
            break
    
    elapsed = time.time() - start
    print(f"\n{'='*50}", flush=True)
    print(f"TIME: {elapsed:.0f}s", flush=True)
    print(f"Data: token={login_data['redemption_token'][:20] if login_data['redemption_token'] else 'N/A'}...", flush=True)
    
    cookies = ctx.cookies()
    rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
    print(f"ROBLOSECURITY: {len(rs)}", flush=True)
    if rs:
        print(f"VALUE: {rs[0]['value'][:50]}...", flush=True)
    else:
        names = [c["name"] + "=" + c["value"][:20] for c in cookies]
        print(f"Cookies: {names}", flush=True)
    print(f"{'='*50}", flush=True)
    
    browser.close()
