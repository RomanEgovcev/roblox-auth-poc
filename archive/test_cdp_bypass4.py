"""CDP bypass full flow: intercept login POST, solve puzzle externally."""
import os, time, json, uuid, re
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
import httpx

def solve_pow(N_str, A, T):
    N = int(N_str)
    val = A % N
    for i in range(T):
        val = (val * val) % N
    return val

def make_handle(ctx, result):
    def do_handle(route, request):
        try:
            _handle(route, request, ctx, result)
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"[HANDLER ERR] {e}", flush=True)
            try: route.continue_()
            except: pass
    return do_handle

def _handle(route, request, ctx, result):
    req_headers = dict(request.headers)
    body_str = request.post_data or "{}"
    body_data = json.loads(body_str)
    csrf = req_headers.get("x-csrf-token", "")
    
    print(f"[HANDLER] Login: {body_data.get('ctype','?')} csrf={csrf[:20]}...", flush=True)
    
    # Get browser cookies for httpx
    browser_cookies = {c["name"]: c["value"] for c in ctx.cookies()}
    h = httpx.Client(cookies=browser_cookies, verify=True, timeout=60)
    
    login_url = "https://auth.roblox.com/v2/login?urlLocale=en_us"
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://www.roblox.com",
        "X-CSRF-TOKEN": csrf,
    }
    
    # Step 1: Forward login request
    r1 = h.post(login_url, json=body_data, headers=hdrs, follow_redirects=False)
    print(f"[HANDLER] 1st attempt: {r1.status_code}", flush=True)
    
    if r1.status_code != 403 or "rblx-challenge-id" not in r1.headers:
        print(f"[HANDLER] No challenge needed", flush=True)
        _fulfill(route, r1)
        return
    
    challenge_id = r1.headers.get("rblx-challenge-id", "")
    challenge_type = r1.headers.get("rblx-challenge-type", "")
    csrf = r1.headers.get("x-csrf-token", csrf)
    print(f"[HANDLER] Challenge: type={challenge_type} id={challenge_id}", flush=True)
    
    # Step 2: Fetch puzzle with proper browser-like headers
    session_id = str(uuid.uuid4())
    
    puzzle_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.roblox.com",
        "Referer": "https://www.roblox.com/login",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }
    
    puzzle_url = f"https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"
    url = f"{puzzle_url}?urlLocale=en_us&sessionID={session_id}"
    print(f"[HANDLER] Puzzle GET session={session_id[:20]}...", flush=True)
    r2 = h.get(url, headers=puzzle_headers, timeout=30)
    print(f"[HANDLER] Puzzle: {r2.status_code} {r2.text[:200]}", flush=True)
    
    if r2.status_code != 200:
        print(f"[HANDLER] Puzzle failed: {r2.text[:200]}", flush=True)
        _fulfill(route, r1)
        return
    
    puzzle_data = r2.json()
    artifacts = json.loads(puzzle_data.get("artifacts", "{}"))
    print(f"[HANDLER] N={str(artifacts['N'])[:30]}... T={artifacts['T']}", flush=True)
    
    # Step 3: Solve puzzle
    answer = solve_pow(artifacts["N"], artifacts["A"], artifacts["T"])
    print(f"[HANDLER] Solved: {str(answer)[:20]}...", flush=True)
    
    # Step 4: Verify
    verify_url = f"https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle/{session_id}/verify"
    r3 = h.post(verify_url, json={"answer": str(answer)}, timeout=30)
    print(f"[HANDLER] Verify: {r3.status_code} {r3.text[:200]}", flush=True)
    
    token = None
    if r3.status_code == 200:
        result_data = r3.json()
        if result_data.get("answerCorrect") and result_data.get("redemptionToken"):
            token = result_data["redemptionToken"]
    
    if not token:
        print("[HANDLER] No token", flush=True)
        _fulfill(route, r1)
        return
    
    print(f"[HANDLER] Token: {token[:30]}...", flush=True)
    
    # Step 5: Call /challenge/v1/continue
    # Try different body formats
    continue_formats = [
        {"challengeId": challenge_id, "redemptionToken": token, "challengeType": challenge_type},
        {"challengeId": challenge_id, "redemptionToken": token},
        {"challengeId": challenge_id, "redemptionToken": token, "type": challenge_type},
        {"challengeId": challenge_id.split("us-central-")[-1] if "us-central-" in challenge_id else challenge_id, "redemptionToken": token},
    ]
    
    continue_success = False
    for fmt in continue_formats:
        continue_url = "https://apis.roblox.com/challenge/v1/continue?urlLocale=en_us"
        r4 = h.post(continue_url, json=fmt, headers={
            **hdrs,
            "X-CSRF-TOKEN": csrf,
        }, timeout=30)
        print(f"[HANDLER] Continue ({json.dumps(fmt)[:80]}): {r4.status_code} {r4.text[:150]}", flush=True)
        if r4.status_code == 200:
            continue_success = True
            break
    
    # Step 6: Retry login with challenge headers
    retry_hdrs = {
        **hdrs,
        "rblx-challenge-id": challenge_id,
        "rblx-challenge-type": challenge_type,
        "rblx-challenge-redemption-token": token,
        "X-CSRF-TOKEN": csrf,
    }
    r5 = h.post(login_url, json=body_data, headers=retry_hdrs, follow_redirects=False)
    print(f"[HANDLER] Retry: {r5.status_code} {r5.text[:300]}", flush=True)
    
    # Check for Set-Cookie with .ROBLOSECURITY
    set_cookie = r5.headers.get("set-cookie", "")
    if ".ROBLOSECURITY" in set_cookie:
        print(f"[HANDLER] SUCCESS! ROBLOSECURITY COOKIE SET!", flush=True)
        result["success"] = True
        result["cookie"] = [v for v in set_cookie.split(";") if ".ROBLOSECURITY" in v]
    
    _fulfill(route, r5)

def _fulfill(route, resp):
    hdrs = {}
    for name, value in resp.headers.items():
        lname = name.lower()
        if lname in ("transfer-encoding", "content-encoding", "content-security-policy"):
            continue
        if lname == "set-cookie":
            if name in hdrs:
                hdrs[name] += f", {value}"
            else:
                hdrs[name] = value
        else:
            hdrs[name] = value
    hdrs["Content-Length"] = str(len(resp.content))
    route.fulfill(status=resp.status_code, headers=hdrs, body=resp.content)

# Main
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    result = {"success": False, "cookie": None}
    page.route("**/v2/login*", make_handle(ctx, result))
    
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
    
    time.sleep(15)
    
    print(f"\n{'='*50}", flush=True)
    print(f"Result: {result}", flush=True)
    
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
