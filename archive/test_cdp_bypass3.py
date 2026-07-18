"""CDP bypass: Fix session ID extraction and fulfill function."""
import os, time, json, httpx, uuid
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

def solve_pow(N_str, A, T):
    N = int(N_str)
    val = A % N
    for i in range(T):
        val = (val * val) % N
        if i % 100000 == 0:
            print(f"  Solve: {100*i//T}%", flush=True)
    print(f"  Solve: 100%", flush=True)
    return val

def do_handle(route, request, ctx):
    try:
        _handle(route, request, ctx)
    except Exception as e:
        print(f"[HANDLER ERR] {e}", flush=True)
        import traceback; traceback.print_exc()
        try: route.continue_()
        except: pass

def _handle(route, request, ctx):
    print(f"[HANDLER] {request.method} {request.url}", flush=True)
    
    if request.method != "POST":
        route.continue_()
        return
    
    req_headers = dict(request.headers)
    
    # Pass through retries with challenge headers
    if "rblx-challenge-id" in req_headers:
        print("[HANDLER] Retry pass-through", flush=True)
        route.continue_()
        return
    
    body_str = request.post_data or "{}"
    body_data = json.loads(body_str) if isinstance(body_str, str) else body_str
    csrf = req_headers.get("x-csrf-token", "")
    
    print(f"[HANDLER] Login: {body_data.get('ctype','?')}", flush=True)
    
    # httpx client with browser cookies
    browser_cookies = {c["name"]: c["value"] for c in ctx.cookies()}
    h = httpx.Client(cookies=browser_cookies, verify=True, timeout=60)
    
    # Step 1: Forward login
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
        print(f"[HANDLER] No challenge: {r1.status_code}", flush=True)
        _fulfill(route, r1)
        return
    
    challenge_id = r1.headers.get("rblx-challenge-id", "")
    print(f"[HANDLER] Challenge: {challenge_id}", flush=True)  # Print FULL value
    
    csrf = r1.headers.get("x-csrf-token", csrf)
    
    # Step 2: Try session from challenge_id (after "us-central-")
    # Then try other approaches if that fails
    session_id = challenge_id.split("us-central-")[-1].strip() if "us-central-" in challenge_id else challenge_id
    
    # Also try without any session ID parameter
    puzzle_url_base = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle?urlLocale=en_us"
    puzzle_url = f"{puzzle_url_base}&sessionID={session_id}"
    
    for attempt_url in [puzzle_url, puzzle_url_base]:
        print(f"[HANDLER] Puzzle GET: {attempt_url[:100]}...", flush=True)
        r2 = h.get(attempt_url, timeout=30)
        print(f"[HANDLER] Puzzle: {r2.status_code} {r2.text[:200]}", flush=True)
        
        if r2.status_code == 200:
            break
    
    if r2.status_code != 200:
        print("[HANDLER] Puzzle failed", flush=True)
        _fulfill(route, r1)
        return
    
    puzzle_data = r2.json()
    artifacts = json.loads(puzzle_data.get("artifacts", "{}"))
    print(f"[HANDLER] N={str(artifacts['N'])[:30]}... T={artifacts['T']}", flush=True)
    
    # Step 3: Solve
    answer = solve_pow(artifacts["N"], artifacts["A"], artifacts["T"])
    
    # Step 4: Verify
    verify_url = f"https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle/{session_id}/verify"
    print(f"[HANDLER] Verify POST: {verify_url}", flush=True)
    r3 = h.post(verify_url, json={"answer": str(answer)}, timeout=30)
    print(f"[HANDLER] Verify: {r3.status_code} {r3.text[:200]}", flush=True)
    
    token = None
    if r3.status_code == 200:
        result = r3.json()
        if result.get("answerCorrect") and result.get("redemptionToken"):
            token = result["redemptionToken"]
    
    if not token:
        print("[HANDLER] Verify failed - no token", flush=True)
        _fulfill(route, r1)
        return
    
    print(f"[HANDLER] Redemption token: {token[:20]}...", flush=True)
    
    # Step 5: Retry login with challenge headers
    retry_hdrs = {
        **hdrs,
        "rblx-challenge-id": challenge_id,
        "rblx-challenge-type": "proofofwork",
        "rblx-challenge-redemption-token": token,
        "X-CSRF-TOKEN": csrf,
    }
    r5 = h.post(login_url, json=body_data, headers=retry_hdrs, follow_redirects=False)
    print(f"[HANDLER] Retry: {r5.status_code} {r5.text[:300]}", flush=True)
    
    _fulfill(route, r5)

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

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
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
