"""CDP bypass v5: intercept login POST, solve puzzle externally."""
import os, time, json, uuid
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

chrome_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.roblox.com",
    "Referer": "https://www.roblox.com/login",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors", 
    "Sec-Fetch-Site": "same-site",
}

login_url = "https://auth.roblox.com/v2/login?urlLocale=en_us"
puzzle_url = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    result = {"done": False, "success": False, "cookie": None}
    
    def handle_login(route, request):
        if result["done"]:
            route.continue_()
            return
        
        body_str = request.post_data or "{}"
        body_data = json.loads(body_str)
        csrf = dict(request.headers).get("x-csrf-token", "")
        print(f"[HANDLER] Login: {body_data.get('ctype','?')}", flush=True)
        
        # Get browser cookies
        browser_cookies = {c["name"]: c["value"] for c in ctx.cookies()}
        
        with httpx.Client(cookies=browser_cookies, verify=True, timeout=60) as h:
            # Step 1: Forward login
            hdrs = {**chrome_headers, "Content-Type": "application/json;charset=UTF-8", "X-CSRF-TOKEN": csrf}
            r1 = h.post(login_url, json=body_data, headers=hdrs, follow_redirects=False)
            print(f"[1st] {r1.status_code}", flush=True)
            
            if r1.status_code != 403 or "rblx-challenge-id" not in r1.headers:
                print(f"[No challenge]", flush=True)
                _fulfill(route, r1)
                result["done"] = True
                return
            
            challenge_id = r1.headers.get("rblx-challenge-id", "")
            challenge_type = r1.headers.get("rblx-challenge-type", "")
            csrf = r1.headers.get("x-csrf-token", csrf)
            print(f"[Challenge] {challenge_id}", flush=True)
            
            # Step 2: Fetch puzzle with RANDOM UUID as session
            sid = str(uuid.uuid4())
            url = f"{puzzle_url}?urlLocale=en_us&sessionID={sid}"
            
            puzzle_hdrs = {**chrome_headers}
            r2 = h.get(url, headers=puzzle_hdrs, timeout=30)
            print(f"[Puzzle] {r2.status_code} {r2.text[:150]}", flush=True)
            
            if r2.status_code != 200:
                # Try without session ID (maybe no session needed)
                url2 = f"{puzzle_url}?urlLocale=en_us"
                r2 = h.get(url2, headers=puzzle_hdrs, timeout=30)
                print(f"[Puzzle no session] {r2.status_code} {r2.text[:150]}", flush=True)
            
            if r2.status_code != 200:
                print(f"[Puzzle failed]", flush=True)
                _fulfill(route, r1)
                result["done"] = True
                return
            
            puzzle_data = r2.json()
            artifacts = json.loads(puzzle_data.get("artifacts", "{}"))
            T = artifacts["T"]
            print(f"[Puzzle] T={T} N={str(artifacts['N'])[:30]}...", flush=True)
            
            # Step 3: Solve
            answer = solve_pow(artifacts["N"], artifacts["A"], T)
            print(f"[Solved] {str(answer)[:20]}...", flush=True)
            
            # Step 4: Verify
            verify_url = f"{puzzle_url}/{sid}/verify"
            r3 = h.post(verify_url, json={"answer": str(answer)}, timeout=30)
            print(f"[Verify] {r3.status_code} {r3.text[:200]}", flush=True)
            
            token = None
            if r3.status_code == 200:
                vr = r3.json()
                if vr.get("answerCorrect") and vr.get("redemptionToken"):
                    token = vr["redemptionToken"]
            
            if not token:
                print(f"[No token]", flush=True)
                _fulfill(route, r1)
                result["done"] = True
                return
            
            print(f"[Token] {token[:30]}...", flush=True)
            
            # Step 5: /challenge/v1/continue
            continue_body = {
                "challengeId": challenge_id,
                "redemptionToken": token,
                "challengeType": challenge_type,
            }
            r4 = h.post(f"https://apis.roblox.com/challenge/v1/continue?urlLocale=en_us",
                       json=continue_body, headers=hdrs, timeout=30)
            print(f"[Continue] {r4.status_code} {r4.text[:150]}", flush=True)
            
            # Step 6: Retry login with challenge headers
            retry_hdrs = {**hdrs,
                "rblx-challenge-id": challenge_id,
                "rblx-challenge-type": challenge_type,
                "rblx-challenge-redemption-token": token,
            }
            r5 = h.post(login_url, json=body_data, headers=retry_hdrs, follow_redirects=False)
            print(f"[Retry] {r5.status_code} {r5.text[:300]}", flush=True)
            
            if r5.status_code == 200:
                set_cookie = r5.headers.get("set-cookie", "")
                if ".ROBLOSECURITY" in set_cookie:
                    print(f"[SUCCESS!]", flush=True)
                    result["success"] = True
                    result["cookie"] = set_cookie
            
            _fulfill(route, r5)
            result["done"] = True
    
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
    
    time.sleep(30)
    
    print(f"\n{'='*50}", flush=True)
    print(f"Result: {result}", flush=True)
    
    cookies = ctx.cookies()
    rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
    print(f"ROBLOSECURITY: {len(rs)}", flush=True)
    
    browser.close()
