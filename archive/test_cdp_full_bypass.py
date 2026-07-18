"""CDP-level bypass: intercept login POST, solve challenge, retry, return 200 to page."""
import os, time, json, re, httpx
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

def solve_pow(N_str, A, T):
    """Solve the time-lock puzzle: compute A^(2^T) mod N."""
    N = int(N_str)
    val = A % N
    chunk = max(1, T // 100)
    for i in range(T):
        val = (val * val) % N
        if i % chunk == 0:
            print(f"  Solving: {100*i//T}%", flush=True)
    print(f"  Solving: 100%", flush=True)
    return val

def handle_login_full(route, request, page_context):
    """Intercept the login POST, handle challenge, return 200 response."""
    try:
        print(f"[HANDLER] Intercepted {request.method} {request.url}", flush=True)
        
        # Only handle POST requests
        if request.method != "POST":
            route.continue_()
            return
        
        _do_handle(route, request, page_context)
    except Exception as e:
        print(f"[HANDLER] Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        route.continue_()

def _do_handle(route, request, page_context):
    """Actual handler logic."""
    # Get cookies from the browser context
    cookies = page_context.cookies()
    cookie_jar = {c["name"]: c["value"] for c in cookies}
    
    # Get CSRF token from the request
    req_headers = dict(request.headers)
    csrf_token = req_headers.get("x-csrf-token", "")
    
    # Get request body
    body_str = request.post_data or "{}"
    body_data = json.loads(body_str) if body_str else {}
    print(f"[HANDLER] body={body_data.get('ctype','')}...", flush=True)
    
    # Step 1: Forward the login request via httpx
    headers = {
        "User-Agent": req_headers.get("user-agent", "Mozilla/5.0"),
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://www.roblox.com",
        "X-CSRF-TOKEN": csrf_token,
        "Accept": "application/json, text/plain, */*",
    }
    
    if "rblx-challenge-id" in req_headers:
        # This is a retry - pass through to server directly
        print(f"[HANDLER] Retry request detected, passing through", flush=True)
        route.continue_()
        return
    
    login_url = "https://auth.roblox.com/v2/login?urlLocale=en_us"
    r = httpx.post(login_url, json=body_data, headers=headers, cookies=cookie_jar, timeout=30)
    print(f"[HANDLER] Initial login: {r.status_code}", flush=True)
    
    if r.status_code != 403 or "rblx-challenge-id" not in r.headers:
        # No challenge needed - return as-is
        print(f"[HANDLER] No challenge, returning {r.status_code}", flush=True)
        route.fulfill(
            status=r.status_code,
            headers=dict(r.headers),
            body=r.text
        )
        return
    
    # Challenge needed!
    challenge_id = r.headers.get("rblx-challenge-id", "")
    print(f"[HANDLER] Challenge issued: {challenge_id[:35]}...", flush=True)
    
    # Update CSRF from response
    csrf_token = r.headers.get("x-csrf-token", csrf_token)
    
    # Update cookies with any new cookies from the login response
    for key, val in r.cookies.items():
        cookie_jar[key] = val
    
    # Step 2: Fetch the puzzle - session ID is in the challenge ID
    # Challenge ID format: "us-central-{UUID}"
    session_str = challenge_id.split("us-central-")[-1] if "us-central-" in challenge_id else challenge_id
    # Clean up: remove any non-UUID characters
    session_str = session_str.split(",")[0].strip()
    puzzle_url = f"https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle?urlLocale=en_us&sessionID={session_str}"
    
    # Update cookies with any new cookies from the login response
    for key, val in r.cookies.items():
        cookie_jar[key] = val
    
    puzzle_headers = {
        "User-Agent": req_headers.get("user-agent", "Mozilla/5.0"),
        "Origin": "https://www.roblox.com",
    }
    
    r2 = httpx.get(puzzle_url, headers=puzzle_headers, cookies=cookie_jar, timeout=30)
    if r2.status_code != 200:
        print(f"[HANDLER] Puzzle fetch failed: {r2.status_code} {r2.text[:200]}", flush=True)
        route.fulfill(status=403, body="Puzzle fetch failed")
        return
    
    puzzle_data = r2.json()
    artifacts = json.loads(puzzle_data.get("artifacts", "{}"))
    session_id2 = puzzle_data.get("sessionID", "")
    print(f"[HANDLER] Puzzle: N={str(artifacts.get('N',''))[:30]}... T={artifacts.get('T')} session={session_id2[:20] if session_id2 else 'none'}", flush=True)
    
    # Step 3: Solve the puzzle
    N = artifacts["N"]
    A = artifacts["A"]
    T = artifacts["T"]
    
    print(f"[HANDLER] Solving puzzle (T={T})...", flush=True)
    answer = solve_pow(N, A, T)
    print(f"[HANDLER] Solved! answer={str(answer)[:30]}...", flush=True)
    
    # Step 4: Verify the solution
    verify_body = {
        "sessionID": session_id2,
        "answer": str(answer),
        "puzzleType": puzzle_data.get("puzzleType", "1")
    }
    
    r3 = httpx.post(puzzle_url, json=verify_body, headers={**puzzle_headers, "Content-Type": "application/json"}, cookies=cookie_jar, timeout=30)
    print(f"[HANDLER] Verify: {r3.status_code} {r3.text[:300]}", flush=True)
    
    redemption_token = None
    if r3.status_code == 200:
        result = r3.json()
        if result.get("answerCorrect") and result.get("redemptionToken"):
            redemption_token = result["redemptionToken"]
    
    if not redemption_token:
        print(f"[HANDLER] Verification failed, trying alternate endpoint...", flush=True)
        # Try with session ID in URL
        alt_url = f"https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle/{session_id2}/verify"
        r4 = httpx.post(alt_url, json={"answer": str(answer)}, headers=puzzle_headers, cookies=cookie_jar, timeout=30)
        print(f"[HANDLER] Alt verify: {r4.status_code} {r4.text[:300]}", flush=True)
        if r4.status_code == 200:
            result = r4.json()
            if result.get("answerCorrect") and result.get("redemptionToken"):
                redemption_token = result["redemptionToken"]
    
    if not redemption_token:
        print(f"[HANDLER] Could not obtain redemption token", flush=True)
        route.fulfill(status=403, body="Challenge failed")
        return
    
    print(f"[HANDLER] Got redemption token: {redemption_token[:20]}...", flush=True)
    
    # Step 5: Retry the login with challenge headers
    retry_headers = {
        **headers,
        "rblx-challenge-id": challenge_id,
        "rblx-challenge-type": "proofofwork",
        "rblx-challenge-redemption-token": redemption_token,
        "X-CSRF-TOKEN": csrf_token,
    }
    
    r5 = httpx.post(login_url, json=body_data, headers=retry_headers, cookies=cookie_jar, timeout=30)
    print(f"[HANDLER] Retry login: {r5.status_code} {r5.text[:300]}", flush=True)
    
    # Step 6: Return the result to the page
    if r5.status_code == 200:
        print(f"[HANDLER] LOGIN SUCCESS!", flush=True)
    
    # Convert headers to list of tuples (preserves multiple Set-Cookie)
    hdr_list = []
    seen_cookies = set()
    for name, value in r5.headers.items():
        name_lower = name.lower()
        if name_lower in ("transfer-encoding", "content-encoding", "content-security-policy"):
            continue
        if name_lower == "set-cookie":
            # httpx may return combined Set-Cookie, split by comma
            # Each cookie should be separate
            hdr_list.append((name, value))
        else:
            hdr_list.append((name, value))
    
    hdr_list.append(("Content-Length", str(len(r5.content))))
    
    route.fulfill(
        status=r5.status_code,
        headers=hdr_list,
        body=r5.content
    )

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Set up route interception BEFORE loading the page
    page.route("**/v2/login*", lambda route: handle_login_full(route, route.request, page.context))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    print("Page loaded", flush=True)
    
    page.fill('input[name="username"]', 'testuser123')
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
    # Trigger login
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
    
    # Wait for result
    time.sleep(10)
    
    print(f"\n{'='*50}", flush=True)
    cookies = page.context.cookies()
    rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
    print(f"ROBLOSECURITY: {len(rs)}", flush=True)
    if rs:
        val = rs[0]["value"]
        print(f"VALUE: {val[:50]}...", flush=True)
        import httpx
        r = httpx.Client(cookies={".ROBLOSECURITY": val})
        auth = r.get("https://users.roblox.com/v1/users/authenticated")
        print(f"AUTH: {auth.status_code} {auth.text[:200]}", flush=True)
    else:
        names = [(c["name"] + "=" + c["value"][:25]) for c in cookies]
        print(f"Cookies: {names}", flush=True)
    print(f"{'='*50}", flush=True)
    
    browser.close()
