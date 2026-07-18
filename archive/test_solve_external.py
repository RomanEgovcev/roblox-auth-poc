"""Solve puzzle externally when browser gets it, then retry."""
import os, time, json, re
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

captured = {
    "session_id": None,
    "challenge_id": None,
    "challenge_type": None,
    "csrf": None,
    "token": None,
}

def on_resp(resp):
    url = resp.url
    if "/v2/login" in url and resp.status == 403:
        h = resp.headers
        captured["challenge_id"] = h.get("rblx-challenge-id", "")
        captured["challenge_type"] = h.get("rblx-challenge-type", "")
        captured["csrf"] = h.get("x-csrf-token", "")
        print(f"[403] cid={captured['challenge_id']}", flush=True)
    
    if "pow-puzzle" in url and "POST" in resp.request.method:
        try:
            body = resp.text()
            data = json.loads(body)
            if data.get("answerCorrect") and data.get("redemptionToken"):
                captured["token"] = data["redemptionToken"]
                print(f"\n[TOKEN from browser] {captured['token'][:30]}...\n", flush=True)
        except:
            pass

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("response", on_resp)
    
    # Intercept puzzle GET: solve externally; don't intercept POST (verify)
    def handle_puzzle(route, request):
        url = request.url
        if request.method != "GET":
            route.continue_()
            return
        
        m = re.search(r'sessionID=([^&]+)', url)
        if m:
            captured["session_id"] = m.group(1)
            print(f"[PUZZLE session={captured['session_id'][:20]}...]", flush=True)
        
        # Forward and capture response
        browser_cookies = {c["name"]: c["value"] for c in ctx.cookies()}
        h = httpx.Client(cookies=browser_cookies, verify=True, timeout=60)
        
        puzzle_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Origin": "https://www.roblox.com",
            "Referer": "https://www.roblox.com/login",
        }
        r = h.get(url, headers=puzzle_headers, timeout=30)
        print(f"[PUZZLE RESP] {r.status_code}", flush=True)
        
        if r.status_code == 200:
            puzzle_data = r.json()
            artifacts = json.loads(puzzle_data.get("artifacts", "{}"))
            print(f"[PUZZLE DATA] N={str(artifacts['N'])[:30]}... T={artifacts['T']}", flush=True)
            
            # Solve
            answer = solve_pow(artifacts["N"], artifacts["A"], artifacts["T"])
            print(f"[SOLVED] answer={str(answer)[:20]}...", flush=True)
            
            # Verify
            verify_url = f"https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle/{captured['session_id']}/verify"
            r3 = h.post(verify_url, json={"answer": str(answer)}, timeout=30)
            print(f"[VERIFY] {r3.status_code} {r3.text[:200]}", flush=True)
            
            if r3.status_code == 200:
                result = r3.json()
                if result.get("answerCorrect") and result.get("redemptionToken"):
                    captured["token"] = result["redemptionToken"]
                    print(f"[TOKEN from httpx] {captured['token'][:30]}...", flush=True)
        
        # Deliver puzzle to browser (browser might try its own Worker)
        hdrs = dict(r.headers)
        hdrs.pop("transfer-encoding", None)
        hdrs.pop("content-encoding", None)
        hdrs["Content-Length"] = str(len(r.content))
        route.fulfill(status=r.status_code, headers=hdrs, body=r.content)
    
    page.route("**/pow-puzzle*", handle_puzzle)
    
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
    
    # Wait for token
    start = time.time()
    while time.time() - start < 45:
        time.sleep(0.5)
        if captured["token"]:
            break
    
    elapsed = time.time() - start
    print(f"\n[WAIT] {elapsed:.0f}s token={'yes' if captured['token'] else 'no'}", flush=True)
    
    if captured["token"] and captured["challenge_id"]:
        print(f"[RETRYING]", flush=True)
        browser_cookies = {c["name"]: c["value"] for c in ctx.cookies()}
        h = httpx.Client(cookies=browser_cookies, verify=True, timeout=60)
        
        login_url = "https://auth.roblox.com/v2/login?urlLocale=en_us"
        body_data = {"ctype":"Username","username":"testuser123","password":"TestPassword123!"}
        hdrs = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://www.roblox.com",
            "X-CSRF-TOKEN": captured["csrf"],
        }
        
        # /challenge/v1/continue
        rc = h.post("https://apis.roblox.com/challenge/v1/continue?urlLocale=en_us",
                   json={"challengeId": captured["challenge_id"], "redemptionToken": captured["token"],
                         "challengeType": captured["challenge_type"]},
                   headers=hdrs, timeout=30)
        print(f"[CONTINUE] {rc.status_code} {rc.text[:150]}", flush=True)
        
        # Retry login
        retry_hdrs = {**hdrs,
            "rblx-challenge-id": captured["challenge_id"],
            "rblx-challenge-type": captured["challenge_type"],
            "rblx-challenge-redemption-token": captured["token"],
        }
        r5 = h.post(login_url, json=body_data, headers=retry_hdrs, follow_redirects=False)
        print(f"[RETRY] {r5.status_code} {r5.text[:300]}", flush=True)
        
        if r5.status_code == 200:
            set_cookie = r5.headers.get("set-cookie", "")
            print(f"[200 BODY] {r5.text[:200]}", flush=True)
            if ".ROBLOSECURITY" in set_cookie:
                print(f"[SUCCESS!] {set_cookie[:100]}", flush=True)
    
    print(f"\n{'='*50}", flush=True)
    cookies = ctx.cookies()
    rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
    print(f"ROBLOSECURITY: {len(rs)}", flush=True)
    
    browser.close()
