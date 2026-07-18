"""CDP-level bypass: Intercept login POST, handle challenge externally, return success."""
import os, time, json, re, httpx
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

def solve_challenge(cookies_jar, csrf_token, challenge_id):
    """Solve the proofofwork challenge using httpx with browser's cookies."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://www.roblox.com",
        "Referer": "https://www.roblox.com/login",
    }
    
    # Fetch the puzzle
    puzzle_url = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle?urlLocale=en_us"
    r = httpx.get(puzzle_url, cookies=cookies_jar, headers=headers, timeout=30)
    if r.status_code != 200:
        print(f"[PUZZLE GET] {r.status_code}", flush=True)
        return None
    
    puzzle_data = r.json()
    artifacts = json.loads(puzzle_data.get("artifacts", "{}"))
    session_id = puzzle_url.split("sessionID=")[-1] if "sessionID" in puzzle_url else ""
    print(f"[PUZZLE] type={puzzle_data.get('puzzleType')} artifacts keys={list(artifacts.keys())} sessionID={session_id}", flush=True)
    
    # Solve the time-lock puzzle: compute A^(2^T) mod N
    N = int(artifacts["N"])
    A = artifacts["A"]
    T = artifacts["T"]
    
    # Check for session ID in cookie or response
    # Extract session ID from the response headers or cookies
    print(f"[PUZZLE] N={str(N)[:40]}... T={T}", flush=True)
    
    # Solve using Python's pow with modular exponentiation
    # We need to compute: result = A^(2^T) mod N
    # This is in the large integer domain
    # Use Python's pow(A, 2**T, N) - but 2**T is astronomically large
    # Instead we use the time-lock puzzle shortcut:
    # Compute e = 2^T mod phi(N)... but we don't know phi(N)
    # Actually the standard approach: start with A and square T times modulo N
    val = A % N
    for i in range(T):
        val = (val * val) % N
        if i % 100000 == 0:
            print(f"[SOLVING] {i}/{T} ({100*i//T}%)", flush=True)
    
    print(f"[SOLVED] answer computed", flush=True)
    
    # Submit the answer
    verify_data = {
        "sessionID": session_id,
        "answer": str(val),
        "puzzleType": puzzle_data.get("puzzleType")
    }
    
    # First try: POST to pow-puzzle with answer
    r2 = httpx.post(
        puzzle_url,
        json=verify_data,
        cookies=cookies_jar,
        headers={**headers, "Content-Type": "application/json"},
        timeout=30
    )
    print(f"[VERIFY] {r2.status_code} {r2.text[:300]}", flush=True)
    
    if r2.status_code == 200:
        result = r2.json()
        if result.get("answerCorrect") and result.get("redemptionToken"):
            return result["redemptionToken"]
    
    # Try alternate URL patterns
    verify_url = f"https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle/{session_id}/verify"
    r3 = httpx.post(
        verify_url,
        json={"answer": str(val)},
        cookies=cookies_jar,
        headers=headers,
        timeout=30
    )
    print(f"[VERIFY2] {r3.status_code} {r3.text[:300]}", flush=True)
    
    return None

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    csrf_token = None
    challenge_id = None
    
    def handle_response(resp):
        global csrf_token, challenge_id
        url = resp.url
        if "/v2/login" in url:
            csrf = resp.headers.get("x-csrf-token", "")
            if csrf:
                csrf_token = csrf
            if resp.status == 403:
                challenge_id = resp.headers.get("rblx-challenge-id", "")
                print(f"[CHALLENGE] id={challenge_id[:30]}..." if challenge_id else "[NO CHALLENGE ID]", flush=True)
    
    page.on("response", handle_response)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    page.fill('input[name="username"]', 'testuser123')
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
    # Get initial CSRF token
    csrf = page.evaluate("""() => {
        var m = document.querySelector('meta[name="csrf-token"]');
        return m ? m.getAttribute('content') : '';
    }""")
    if csrf:
        csrf_token = csrf
        print(f"[INITIAL CSRF] {csrf[:30]}...", flush=True)
    
    # Get cookies before the POST
    browser_cookies = page.context.cookies()
    cookies_jar = {c["name"]: c["value"] for c in browser_cookies}
    print(f"[COOKIES] {list(cookies_jar.keys())}", flush=True)
    
    # Trigger the initial login POST (we'll see the challenge and get challenge_id + session cookies)
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
    
    # Wait for challenge to appear
    time.sleep(5)
    
    # Update cookies after challenge
    browser_cookies = page.context.cookies()
    cookies_jar = {c["name"]: c["value"] for c in browser_cookies}
    print(f"[POST-CHALLENGE COOKIES] {list(cookies_jar.keys())}", flush=True)
    
    if challenge_id:
        print(f"[SOLVING CHALLENGE] challenge_id={challenge_id[:30]}...", flush=True)
        redemption_token = solve_challenge(cookies_jar, csrf_token, challenge_id)
        
        if redemption_token:
            print(f"[REDEMPTION TOKEN] {redemption_token}", flush=True)
            
            # Now retry the login with the redemption token
            # We'll use page.route to intercept and retry at CDP level
            retry_result = [None]
            
            def retry_handler(route):
                # Get the request body
                body = route.request.post_data or ""
                print(f"[ROUTE] Login POST intercepted. Adding challenge headers.", flush=True)
                
                # Modify headers to include challenge headers
                headers = dict(route.request.headers)
                headers["rblx-challenge-id"] = challenge_id
                headers["rblx-challenge-type"] = "proofofwork"
                headers["rblx-challenge-redemption-token"] = redemption_token
                
                # Continue with modified headers
                route.continue_(headers=headers)
            
            page.route("**/auth.roblox.com/v2/login", retry_handler)
            
            # Make a retry fetch from page context
            result = page.evaluate("""({csrf, body}) => {
                return fetch('https://auth.roblox.com/v2/login?urlLocale=en_us', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json;charset=UTF-8',
                        'X-CSRF-TOKEN': csrf
                    },
                    body: JSON.stringify(body),
                    credentials: 'include'
                }).then(r => r.text().then(t => ({
                    status: r.status,
                    body: t
                }))).catch(e => ({error: e.message}));
            }""", {
                "csrf": csrf_token,
                "body": {
                    "ctype": "username",
                    "cvalue": "testuser123",
                    "password": "TestPassword123!",
                    "secureAuthIntent": True
                }
            })
            
            print(f"[RETRY RESULT] {result}", flush=True)
            page.unroute("**/auth.roblox.com/v2/login")
        else:
            print("[FAIL] Could not solve challenge", flush=True)
    else:
        print("[INFO] No challenge ID found, checking if login succeeded directly...", flush=True)
    
    # Final check
    time.sleep(3)
    cookies = page.context.cookies()
    rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
    if rs:
        print(f"\n[SUCCESS] .ROBLOSECURITY={rs[0]['value'][:50]}...", flush=True)
        r = httpx.Client(cookies={".ROBLOSECURITY": rs[0]["value"]})
        auth = r.get("https://users.roblox.com/v1/users/authenticated")
        print(f"[AUTH] {auth.status_code} {auth.text[:200]}", flush=True)
    else:
        print(f"\n[FAILED] Cookies: {[f'{c[\"name\"]}={c[\"value\"][:20]}' for c in cookies]}", flush=True)
    
    browser.close()
