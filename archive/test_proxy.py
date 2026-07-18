"""
Intercept login POST at CDP level, solve challenge entirely in Python httpx,
and fulfill the success response back to the page.
"""
import os, time, json, base64, httpx

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"
API_URL = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"
AUTH_URL = "https://auth.roblox.com"

def solve_puzzle(N_str, A_str, T_val):
    """Solve Time-Lock puzzle: A^(2^T) mod N"""
    N = int(N_str)
    A = int(A_str)
    result = A
    for _ in range(T_val):
        result = (result * result) % N
    return str(result)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    def handle_login(route):
        if "login" not in route.request.url:
            route.continue_()
            return
        
        print(f"\n[ROUTE] Intercepted: {route.request.method} {route.request.url}", flush=True)
        
        # Get request details
        body = route.request.post_data
        req_url = route.request.url
        
        # Get all browser cookies for this request
        cookies = {c["name"]: c["value"] for c in page.context.cookies()}
        print(f"[ROUTE] Cookies: {list(cookies.keys())}", flush=True)
        
        # Get the CSRF from the original request headers
        req_headers = route.request.headers
        csrf = req_headers.get("x-csrf-token", "")
        print(f"[ROUTE] CSRF: {csrf}", flush=True)
        
        if not csrf or not csrf.strip():
            # This is the pre-check (no CSRF yet) - let it through
            print(f"[ROUTE] No CSRF, continuing...", flush=True)
            route.continue_()
            return
        
        print(f"[ROUTE] Solving challenge via httpx...", flush=True)
        
        # 1. Forward the request via httpx with browser cookies
        with httpx.Client(verify=False, timeout=60) as client:
            for name, value in cookies.items():
                client.cookies.set(name, value, domain=".roblox.com")
            
            headers = {
                "Content-Type": "application/json",
                "x-csrf-token": csrf,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Origin": "https://www.roblox.com",
                "Referer": "https://www.roblox.com/login",
            }
            
            # Forward original request - expect 403 with challenge
            r1 = client.post(req_url, content=body, headers=headers)
            print(f"[ROUTE] Forward response: {r1.status_code}", flush=True)
            
            chall_id = r1.headers.get("rblx-challenge-id", "")
            chall_meta_b64 = r1.headers.get("rblx-challenge-metadata", "")
            
            if r1.status_code != 403 or not chall_id:
                print(f"[ROUTE] No challenge, fulfilling as-is", flush=True)
                route.fulfill(status=r1.status_code, headers=dict(r1.headers), body=r1.text)
                return
            
            # 2. Parse challenge metadata
            meta = json.loads(base64.b64decode(chall_meta_b64))
            session_id = meta["sessionId"]
            print(f"[ROUTE] Challenge: {chall_id}", flush=True)
            print(f"[ROUTE] Session: {session_id}", flush=True)
            
            # 3. Get puzzle
            r2 = client.get(f"{API_URL}?sessionID={session_id}")
            if r2.status_code != 200:
                print(f"[ROUTE] Puzzle GET failed: {r2.status_code}", flush=True)
                route.fulfill(status=r1.status_code, headers=dict(r1.headers), body=r1.text)
                return
            
            puzzle = r2.json()
            artifacts = json.loads(puzzle["artifacts"])
            N, A, T = artifacts["N"], artifacts["A"], artifacts["T"]
            print(f"[ROUTE] Puzzle: N bits={len(N)}, A={A}, T={T}", flush=True)
            
            # 4. Solve puzzle
            print(f"[ROUTE] Computing solution...", flush=True)
            start = time.time()
            answer = solve_puzzle(N, A, T)
            print(f"[ROUTE] Answer ({len(answer)} digits) in {time.time()-start:.1f}s", flush=True)
            
            # 5. Get CSRF for API
            r3 = client.post(API_URL, json={}, headers={"Content-Type": "application/json"})
            api_csrf = r3.headers.get("x-csrf-token", "")
            
            # 6. Submit solution
            r4 = client.post(
                API_URL,
                json={"solution": answer, "sessionId": session_id},
                headers={
                    "Content-Type": "application/json",
                    "x-csrf-token": api_csrf,
                },
            )
            print(f"[ROUTE] Submit: {r4.status_code}", flush=True)
            result_data = r4.json()
            redemption_token = result_data.get("redemptionToken", "")
            print(f"[ROUTE] Redemption token: {redemption_token}", flush=True)
            
            if not redemption_token:
                print(f"[ROUTE] No redemption token!", flush=True)
                route.fulfill(status=r1.status_code, headers=dict(r1.headers), body=r1.text)
                return
            
            # 7. Retry login with redemption token
            headers_with_challenge = dict(headers)
            headers_with_challenge["rblx-challenge-id"] = chall_id
            headers_with_challenge["rblx-challenge-type"] = "proofofwork"
            headers_with_challenge["rblx-challenge-redemption-token"] = redemption_token
            
            r5 = client.post(req_url, content=body, headers=headers_with_challenge)
            print(f"[ROUTE] Retry: {r5.status_code}", flush=True)
            print(f"[ROUTE] Retry body: {r5.text[:200]}", flush=True)
            
            if r5.status_code == 200:
                print(f"\n*** LOGIN SUCCESS via httpx! ***", flush=True)
                # Get the set-cookie headers for .ROBLOSECURITY
                set_cookies = r5.headers.get_list("set-cookie")
                for sc in set_cookies:
                    print(f"  Set-Cookie: {sc[:100]}...", flush=True)
                
                # Return success to the page
                route.fulfill(
                    status=200,
                    headers={"content-type": "application/json"},
                    body=r5.text,
                )
            else:
                # Return whatever happened
                rsp_headers = dict(r5.headers)
                route.fulfill(status=r5.status_code, headers=rsp_headers, body=r5.text)
    
    # Set up route intercept
    page.route("**/v2/login", handle_login)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    print("Page loaded", flush=True)
    
    # Fill and submit the login form
    page.fill('input[name="username"]', USER)
    page.fill('input[name="password"]', PASS)
    time.sleep(1)
    
    print("Clicking login button...", flush=True)
    page.click('button[type="submit"]')
    
    time.sleep(15)
    print(f"Final URL: {page.url}", flush=True)
    print(f"Title: {page.title()}", flush=True)
    
    time.sleep(3)
    browser.close()
