"""
Full login flow completely in Python httpx using browser cookies.
All requests via httpx = PX JS interception bypassed entirely.
"""
import os, time, json, base64, httpx

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"
API_URL = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"

def solve_puzzle(N_str, A_str, T_val):
    N, A = int(N_str), int(A_str)
    result = A
    for _ in range(T_val):
        result = (result * result) % N
    return str(result)

# ====== Step 1: Get browser cookies by opening the login page ======
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    # Export cookies
    browser_cookies = page.context.cookies()
    cookie_dict = {c["name"]: c["value"] for c in browser_cookies}
    print(f"Browser cookies ({len(cookie_dict)}): {list(cookie_dict.keys())}", flush=True)
    
    browser.close()

# ====== Step 2: Full login flow in httpx ======
print("\n=== Starting httpx flow ===", flush=True)

with httpx.Client(verify=False, timeout=60) as client:
    # Set browser cookies
    for name, value in cookie_dict.items():
        client.cookies.set(name, value, domain=".roblox.com")
    
    # 2a. POST to /v2/login without CSRF to get CSRF token
    login_body = json.dumps({"ctype": "Username", "cvalue": USER, "password": PASS})
    headers_base = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://www.roblox.com",
        "Referer": "https://www.roblox.com/login",
    }
    
    r = client.post("https://auth.roblox.com/v2/login", content=login_body, headers=headers_base)
    csrf = r.headers.get("x-csrf-token", "")
    print(f"CSRF obtained: {csrf}", flush=True)
    
    # 2b. POST with CSRF to trigger challenge
    headers_with_csrf = dict(headers_base)
    headers_with_csrf["x-csrf-token"] = csrf
    
    r = client.post("https://auth.roblox.com/v2/login", content=login_body, headers=headers_with_csrf)
    print(f"Challenge response: {r.status_code}", flush=True)
    
    chall_id = r.headers.get("rblx-challenge-id", "")
    chall_meta_b64 = r.headers.get("rblx-challenge-metadata", "")
    chall_type = r.headers.get("rblx-challenge-type", "")
    print(f"  challenge-id: {chall_id}", flush=True)
    print(f"  challenge-type: {chall_type}", flush=True)
    
    if r.status_code != 403 or not chall_id:
        print(f"  No challenge! Body: {r.text[:200]}", flush=True)
        exit()
    
    # Parse metadata
    meta = json.loads(base64.b64decode(chall_meta_b64))
    session_id = meta["sessionId"]
    generic_chall_id = meta.get("sharedParameters", {}).get("genericChallengeId", "")
    print(f"  sessionId: {session_id}", flush=True)
    print(f"  genericChallengeId: {generic_chall_id}", flush=True)
    
    # 2c. Check cookies after challenge
    print(f"\nCookies after challenge:", flush=True)
    for cookie in client.cookies.jar:
        print(f"  {cookie.name}: {cookie.value[:60]}", flush=True)
    
    # 2d. Get puzzle
    r = client.get(f"{API_URL}?sessionID={session_id}")
    print(f"\nPuzzle GET: {r.status_code}", flush=True)
    
    if r.status_code != 200:
        print(f"  Failed! Body: {r.text[:200]}", flush=True)
        exit()
    
    puzzle = r.json()
    artifacts = json.loads(puzzle["artifacts"])
    N, A, T = artifacts["N"], artifacts["A"], artifacts["T"]
    print(f"  N bits={int(N).bit_length()}, A={A}, T={T}", flush=True)
    
    # 2e. Solve
    print(f"Computing...", flush=True)
    start = time.time()
    answer = solve_puzzle(N, A, T)
    print(f"Answer ({len(answer)} digits) in {time.time()-start:.1f}s", flush=True)
    
    # 2f. Get CSRF for API
    r = client.post(API_URL, json={}, headers={"Content-Type": "application/json"})
    api_csrf = r.headers.get("x-csrf-token", "")
    print(f"\nAPI CSRF: {api_csrf}", flush=True)
    
    # 2g. Submit solution
    r = client.post(
        API_URL,
        json={"solution": answer, "sessionId": session_id},
        headers={"Content-Type": "application/json", "x-csrf-token": api_csrf},
    )
    print(f"Submit: {r.status_code}", flush=True)
    submit_data = r.json()
    redemption_token = submit_data.get("redemptionToken", "")
    print(f"  answerCorrect: {submit_data.get('answerCorrect')}", flush=True)
    print(f"  redemptionToken: {redemption_token}", flush=True)
    
    if not redemption_token:
        print("No redemption token!", flush=True)
        exit()
    
    # ====== Step 3: RETRY LOGIN WITH CHALLENGE HEADERS ======
    print(f"\n=== Retrying login with redemption token ===", flush=True)
    
    # 3a. Get fresh CSRF (in case old one expired)
    r = client.post("https://auth.roblox.com/v2/login", content=login_body, headers=headers_base)
    csrf2 = r.headers.get("x-csrf-token", "")
    print(f"Fresh CSRF: {csrf2}", flush=True)
    
    # 3b. Retry with challenge headers
    retry_headers = dict(headers_base)
    retry_headers["x-csrf-token"] = csrf2
    retry_headers["rblx-challenge-id"] = chall_id
    retry_headers["rblx-challenge-type"] = "proofofwork"
    retry_headers["rblx-challenge-redemption-token"] = redemption_token
    
    print(f"Retry headers:", flush=True)
    for k, v in retry_headers.items():
        if k.lower() in ("x-csrf-token", "rblx-challenge-id", "rblx-challenge-type", "rblx-challenge-redemption-token", "content-type"):
            print(f"  {k}: {v}", flush=True)
    
    r = client.post("https://auth.roblox.com/v2/login", content=login_body, headers=retry_headers)
    print(f"\nLogin retry: {r.status_code}", flush=True)
    print(f"Response headers:", flush=True)
    for k, v in r.headers.items():
        print(f"  {k}: {v}", flush=True)
    print(f"Body: {r.text[:500]}", flush=True)
    
    if r.status_code == 200:
        print("\n*** LOGIN SUCCESS! ***", flush=True)
        # Print .ROBLOSECURITY cookie
        for cookie in client.cookies.jar:
            if cookie.name == ".ROBLOSECURITY":
                print(f"\n  .ROBLOSECURITY: {cookie.value[:50]}...", flush=True)
    else:
        # Try with original CSRF too
        print(f"\nTrying with original CSRF...", flush=True)
        retry_headers["x-csrf-token"] = csrf  # original CSRF
        r = client.post("https://auth.roblox.com/v2/login", content=login_body, headers=retry_headers)
        print(f"Login retry (orig CSRF): {r.status_code}", flush=True)
        print(f"Body: {r.text[:300]}", flush=True)
        
        # Try with genericChallengeId as chall_id
        if generic_chall_id:
            print(f"\nTrying with genericChallengeId...", flush=True)
            retry_headers["x-csrf-token"] = csrf2
            retry_headers["rblx-challenge-id"] = generic_chall_id
            r = client.post("https://auth.roblox.com/v2/login", content=login_body, headers=retry_headers)
            print(f"Login retry (generic id): {r.status_code}", flush=True)
            print(f"Body: {r.text[:300]}", flush=True)
    
    time.sleep(2)
