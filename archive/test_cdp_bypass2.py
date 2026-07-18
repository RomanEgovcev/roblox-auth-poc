"""CDP bypass: intercept login POST, solve puzzle via httpx, return 200."""
import os, time, json, httpx, uuid
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

def solve_pow(N_str, A, T):
    N = int(N_str)
    val = A % N
    for i in range(T):
        val = (val * val) % N
        if i % 50000 == 0:
            print(f"  Solve: {100*i//T}%", flush=True)
    print(f"  Solve: 100%", flush=True)
    return val

def do_handle(route, request, ctx):
    """Intercept login POST, handle challenge, return 200."""
    print(f"[HANDLER] Intercepted {request.method} {request.url}", flush=True)
    
    if request.method != "POST":
        route.continue_()
        return
    
    # Build httpx client with cookies from browser
    browser_cookies = {c["name"]: c["value"] for c in ctx.cookies()}
    
    req_headers = dict(request.headers)
    csrf = req_headers.get("x-csrf-token", "")
    body_str = request.post_data or "{}"
    body_data = json.loads(body_str) if isinstance(body_str, str) else body_str
    
    # Check if this is a retry with challenge headers
    if "rblx-challenge-id" in req_headers:
        print(f"[HANDLER] Retry - passing through", flush=True)
        route.continue_()
        return
    
    print(f"[HANDLER] Login POST for {body_data.get('ctype','?')}", flush=True)
    
    # httpx client with cookies
    h = httpx.Client(cookies=browser_cookies, verify=True, timeout=60)
    
    # Step 1: Forward login request
    login_url = "https://auth.roblox.com/v2/login?urlLocale=en_us"
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://www.roblox.com",
        "X-CSRF-TOKEN": csrf,
    }
    r1 = h.post(login_url, json=body_data, headers=hdrs, follow_redirects=False)
    print(f"[HANDLER] Initial: {r1.status_code}", flush=True)
    
    if r1.status_code != 403 or "rblx-challenge-id" not in r1.headers:
        print(f"[HANDLER] No challenge, returning {r1.status_code}", flush=True)
        _fulfill(route, r1)
        return
    
    challenge_id = r1.headers.get("rblx-challenge-id", "")
    print(f"[HANDLER] Challenge: {challenge_id[:40]}...", flush=True)
    print(f"[HANDLER] 403 body: {r1.text[:500]}", flush=True)  # DEBUG
    
    # Update CSRF
    csrf = r1.headers.get("x-csrf-token", csrf)
    
    # Step 2: Fetch puzzle - session ID is client-generated UUID
    session_id = str(uuid.uuid4())
    puzzle_url = f"https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle?urlLocale=en_us&sessionID={session_id}"
    print(f"[HANDLER] Generated session: {session_id}", flush=True)
    
    r2 = h.get(puzzle_url, timeout=30)
    print(f"[HANDLER] Puzzle: {r2.status_code}", flush=True)
    
    if r2.status_code != 200:
        print(f"[HANDLER] Puzzle fail: {r2.text[:200]}", flush=True)
        _fulfill(route, r1)  # Return original 403
        return
    
    puzzle_data = r2.json()
    artifacts = json.loads(puzzle_data.get("artifacts", "{}"))
    print(f"[HANDLER] N={str(artifacts.get('N',''))[:30]}... T={artifacts.get('T')}", flush=True)
    
    # Step 3: Solve puzzle (T modular squarings)
    answer = solve_pow(artifacts["N"], artifacts["A"], artifacts["T"])
    print(f"[HANDLER] Answer computed", flush=True)
    
    # Step 4: Verify solution
    verify_body = {
        "sessionID": session_id,
        "answer": str(answer),
        "puzzleType": puzzle_data.get("puzzleType", "1")
    }
    r3 = h.post(puzzle_url, json=verify_body, headers={"Content-Type": "application/json", "Origin": "https://www.roblox.com"}, timeout=30)
    print(f"[HANDLER] Verify: {r3.status_code} {r3.text[:200]}", flush=True)
    
    token = None
    if r3.status_code == 200:
        result = r3.json()
        if result.get("answerCorrect") and result.get("redemptionToken"):
            token = result["redemptionToken"]
    
    if not token:
        print(f"[HANDLER] Verify failed, trying alt endpoint", flush=True)
        r4 = h.post(
            f"https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle/{session_id}/verify",
            json={"answer": str(answer)},
            timeout=30
        )
        print(f"[HANDLER] Alt verify: {r4.status_code} {r4.text[:200]}", flush=True)
        if r4.status_code == 200:
            result = r4.json()
            if result.get("answerCorrect") and result.get("redemptionToken"):
                token = result["redemptionToken"]
    
    if not token:
        print(f"[HANDLER] Could not verify puzzle", flush=True)
        _fulfill(route, r1)
        return
    
    print(f"[HANDLER] Token: {token[:20]}...", flush=True)
    
    # Step 5: Retry login with challenge headers
    retry_hdrs = {
        **hdrs,
        "rblx-challenge-id": challenge_id,
        "rblx-challenge-type": "proofofwork",
        "rblx-challenge-redemption-token": token,
        "X-CSRF-TOKEN": csrf,
    }
    r5 = h.post(login_url, json=body_data, headers=retry_hdrs, follow_redirects=False)
    print(f"[HANDLER] Retry: {r5.status_code} {r5.text[:200]}", flush=True)
    
    # Step 6: Return response to browser
    _fulfill(route, r5)

def _fulfill(route, resp):
    """Fulfill the route with the httpx response."""
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

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Intercept login POST
    page.route("**/v2/login*", lambda route: do_handle(route, route.request, ctx))
    
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
    
    time.sleep(15)
    
    print(f"\n{'='*50}", flush=True)
    cookies = ctx.cookies()
    rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
    print(f"ROBLOSECURITY: {len(rs)}", flush=True)
    if rs:
        val = rs[0]["value"]
        print(f"VALUE: {val[:50]}...", flush=True)
        r = httpx.Client(cookies={".ROBLOSECURITY": val})
        auth = r.get("https://users.roblox.com/v1/users/authenticated")
        print(f"AUTH: {auth.status_code} {auth.text[:200]}", flush=True)
    else:
        names = [c["name"] + "=" + c["value"][:25] for c in cookies]
        print(f"Cookies: {names}", flush=True)
    print(f"{'='*50}", flush=True)
    
    browser.close()
