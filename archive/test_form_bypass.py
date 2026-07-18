"""
Bypass PX entirely using browser-native form submission.
Form submissions go through navigation stack, NOT through fetch/XHR.
Route handler intercepts and handles challenge cycle in httpx.
"""
import os, time, json, base64, urllib.parse, httpx

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

state = {"login_success": False, "done": False}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    def handle_login(route):
        if "/v2/login" not in route.request.url or route.request.method != "POST":
            route.continue_()
            return
        
        body = route.request.post_data or ""
        req_url = route.request.url
        headers = dict(route.request.headers)
        
        print(f"\n[ROUTE] POST {req_url}", flush=True)
        
        if state["login_success"]:
            print("[ROUTE] Already logged in, dropping", flush=True)
            route.continue_()
            return
        
        # Get browser cookies once
        cookies = {c["name"]: c["value"] for c in page.context.cookies()}
        print(f"[ROUTE] Cookies: {list(cookies.keys())}", flush=True)
        
        # Parse form data
        parsed = urllib.parse.parse_qs(body)
        data = {k: v[0] for k, v in parsed.items()}
        print(f"[ROUTE] Data: ctype={data.get('ctype')}, cvalue={data.get('cvalue')}", flush=True)
        
        json_body = json.dumps(data)
        
        with httpx.Client(verify=False, timeout=120) as client:
            for name, value in cookies.items():
                client.cookies.set(name, value, domain=".roblox.com")
            
            hdrs = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Origin": "https://www.roblox.com",
                "Referer": "https://www.roblox.com/login",
            }
            
            # Get CSRF
            r = client.post(req_url, content=json_body, headers=hdrs)
            csrf = r.headers.get("x-csrf-token", "")
            print(f"[ROUTE] CSRF: {csrf[:20]} (status={r.status_code})", flush=True)
            
            if not csrf:
                print("[ROUTE] No CSRF!", flush=True)
                route.fulfill(status=r.status_code, headers=dict(r.headers), body=r.text)
                state["done"] = True
                return
            
            # Trigger challenge
            hdrs["x-csrf-token"] = csrf
            r = client.post(req_url, content=json_body, headers=hdrs)
            chall_id = r.headers.get("rblx-challenge-id", "")
            print(f"[ROUTE] Challenge: {r.status_code}, id={chall_id}", flush=True)
            
            if r.status_code == 200:
                state["login_success"] = True
                print(f"\n*** LOGIN SUCCESS! ***", flush=True)
                route.fulfill(status=200, headers={"content-type": "application/json"}, body=r.text)
                state["done"] = True
                return
            
            if r.status_code != 403 or not chall_id:
                print(f"[ROUTE] Unexpected response: {r.text[:200]}", flush=True)
                route.fulfill(status=r.status_code, headers=dict(r.headers), body=r.text)
                state["done"] = True
                return
            
            # Parse challenge
            meta = json.loads(base64.b64decode(r.headers["rblx-challenge-metadata"]))
            session_id = meta["sessionId"]
            print(f"[ROUTE] Session: {session_id}", flush=True)
            
            # Get & solve puzzle
            r2 = client.get(f"{API_URL}?sessionID={session_id}")
            if r2.status_code != 200:
                route.fulfill(status=r.status_code, headers=dict(r.headers), body=r.text)
                state["done"] = True
                return
            
            puzzle = r2.json()
            artifacts = json.loads(puzzle["artifacts"])
            N, A, T = artifacts["N"], artifacts["A"], artifacts["T"]
            print(f"[ROUTE] Puzzle: N bits={int(N).bit_length()}, T={T}", flush=True)
            
            start = time.time()
            answer = solve_puzzle(N, A, T)
            print(f"[ROUTE] Solved in {time.time()-start:.1f}s ({len(answer)} digits)", flush=True)
            
            # Submit solution
            r3 = client.post(API_URL, json={}, headers={"Content-Type": "application/json"})
            api_csrf = r3.headers.get("x-csrf-token", "")
            r4 = client.post(
                API_URL,
                json={"solution": answer, "sessionId": session_id},
                headers={"Content-Type": "application/json", "x-csrf-token": api_csrf},
            )
            redemption = r4.json().get("redemptionToken", "")
            print(f"[ROUTE] Redemption: {redemption}", flush=True)
            
            if not redemption:
                route.fulfill(status=r.status_code, headers=dict(r.headers), body=r.text)
                state["done"] = True
                return
            
            # Retry
            hdrs["rblx-challenge-id"] = chall_id
            hdrs["rblx-challenge-type"] = "proofofwork"
            hdrs["rblx-challenge-redemption-token"] = redemption
            
            r5 = client.post(req_url, content=json_body, headers=hdrs)
            print(f"[ROUTE] Retry: {r5.status_code} {r5.text[:200]}", flush=True)
            
            if r5.status_code == 200:
                state["login_success"] = True
                print(f"\n*** LOGIN SUCCESS! ***", flush=True)
                for cookie in client.cookies.jar:
                    if cookie.name == ".ROBLOSECURITY":
                        print(f"  .ROBLOSECURITY: {cookie.value[:60]}...", flush=True)
            
            route.fulfill(
                status=r5.status_code,
                headers={"content-type": "application/json", "access-control-allow-origin": "*"},
                body=r5.text,
            )
            state["done"] = True
    
    page.route("**/v2/login", handle_login)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    print("Page loaded", flush=True)
    
    # Submit form to bypass PX
    result = page.evaluate("""() => {
        const iframe = document.createElement('iframe');
        iframe.name = 'login-target';
        iframe.style.display = 'none';
        document.body.appendChild(iframe);
        
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = 'https://auth.roblox.com/v2/login';
        form.target = 'login-target';
        
        const fields = {ctype: 'Username', cvalue: '""" + USER + """', password: '""" + PASS + """'};
        for (const [k, v] of Object.entries(fields)) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = k;
            input.value = v;
            form.appendChild(input);
        }
        
        document.body.appendChild(form);
        form.submit();
        return 'submitted';
    }""")
    print(f"Form: {result}", flush=True)
    
    # Wait for completion
    for _ in range(60):
        if state["done"]:
            break
        time.sleep(1)
    
    print(f"\nFinal URL: {page.url}", flush=True)
    print(f"Login success: {state['login_success']}", flush=True)
    
    time.sleep(5)
    browser.close()
