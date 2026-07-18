"""
Full flow: challenge in browser -> puzzle solve in Python httpx (outside browser)
-> retry in browser (preserving PX cookies).
This way the browser's PX state is NOT modified by puzzle requests.
"""
import os, time, json, base64, httpx

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"
API_URL = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    # 1. Get CSRF
    csrf = page.evaluate("""() => {
        return fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ctype:'Username', cvalue:'""" + USER + """', password:'""" + PASS + """'}),
        }).then(r => r.headers.get('x-csrf-token'));
    }""")
    print(f"Auth CSRF: {csrf}", flush=True)
    
    # 2. Get challenge
    chall = page.evaluate("""async () => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json', 'x-csrf-token': '""" + csrf + """'},
            body: JSON.stringify({ctype:'Username', cvalue:'""" + USER + """', password:'""" + PASS + """'}),
        });
        const h = {};
        r.headers.forEach((v,k) => { h[k.toLowerCase()] = v; });
        const meta = h['rblx-challenge-metadata'] || '';
        let sid = '';
        try { sid = JSON.parse(atob(meta)).sessionId; } catch(e) {}
        return {challId: h['rblx-challenge-id'], sessionId: sid};
    }""")
    chall_id = chall["challId"]
    session_id = chall["sessionId"]
    print(f"Challenge: {chall_id}", flush=True)
    print(f"Session: {session_id}", flush=True)
    
    # Export cookies for httpx
    cookies_list = page.context.cookies()
    cookie_dict = {c["name"]: c["value"] for c in cookies_list}
    print(f"Browser cookies: {list(cookie_dict.keys())}", flush=True)
    
    # 3. Solve puzzle using httpx (outside browser - doesn't modify browser PX state)
    print(f"\nFetching puzzle via httpx...", flush=True)
    with httpx.Client(verify=False, timeout=30) as client:
        # Set browser cookies
        for name, value in cookie_dict.items():
            client.cookies.set(name, value, domain=".roblox.com")
        
        # GET puzzle
        r = client.get(f"{API_URL}?sessionID={session_id}")
        print(f"GET puzzle: {r.status_code}", flush=True)
        puzzle_data = r.json()
        artifacts = json.loads(puzzle_data["artifacts"])
        N, A, T = int(artifacts["N"]), int(artifacts["A"]), int(artifacts["T"])
        print(f"Puzzle: N bits={N.bit_length()}, A={A}, T={T}", flush=True)
        
        # Solve
        print(f"Computing...", flush=True)
        start = time.time()
        result = A
        for i in range(T):
            result = (result * result) % N
        answer = str(result)
        print(f"Answer ({len(answer)} digits) in {time.time()-start:.1f}s", flush=True)
        
        # Get CSRF for API
        r = client.post(API_URL, json={})
        csrf_api = r.headers.get("x-csrf-token", "")
        print(f"API CSRF: {csrf_api}", flush=True)
        
        # POST solution
        r = client.post(
            API_URL,
            json={"solution": answer, "sessionId": session_id},
            headers={"x-csrf-token": csrf_api, "Content-Type": "application/json"},
        )
        print(f"POST solution: {r.status_code}", flush=True)
        result_data = r.json()
        print(f"  Result: {json.dumps(result_data, indent=2)}", flush=True)
        
        redemption_token = result_data.get("redemptionToken", "")
        if not redemption_token:
            print("No redemption token!", flush=True)
            # Try without CSRF
            r = client.post(
                API_URL,
                json={"solution": answer, "sessionId": session_id},
                headers={"Content-Type": "application/json"},
            )
            print(f"  Retry without CSRF: {r.status_code}", flush=True)
            result_data = r.json()
            print(f"  Result: {json.dumps(result_data, indent=2)}", flush=True)
            redemption_token = result_data.get("redemptionToken", "")
        
        if not redemption_token:
            print("No redemption token!", flush=True)
            browser.close()
            exit()
        
        print(f"\nRedemption token: {redemption_token}", flush=True)
        
        # 4. Now retry in the browser (PX state unchanged)
        print(f"\nRetrying login in browser...", flush=True)
        
        # First get fresh CSRF
        csrf3 = page.evaluate("""() => {
            return fetch('https://auth.roblox.com/v2/login', {
                method: 'POST', credentials: 'include',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ctype:'Username', cvalue:'""" + USER + """', password:'""" + PASS + """'}),
            }).then(r => r.headers.get('x-csrf-token'));
        }""")
        print(f"Fresh CSRF: {csrf3}", flush=True)
        
        # Now login with challenge headers
        login = page.evaluate("""async () => {
            const chall_id = '""" + chall_id + """';
            const redemption_token = '""" + redemption_token + """';
            const csrf = '""" + csrf3 + """';
            const r = await fetch('https://auth.roblox.com/v2/login', {
                method: 'POST', credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'x-csrf-token': csrf,
                    'rblx-challenge-id': chall_id,
                    'rblx-challenge-type': 'proofofwork',
                    'rblx-challenge-redemption-token': redemption_token,
                },
                body: JSON.stringify({ctype:'Username', cvalue:'""" + USER + """', password:'""" + PASS + """'})
            });
            const hdrs = {};
            r.headers.forEach((v,k) => { hdrs[k.toLowerCase()] = v; });
            return {status: r.status, headers: hdrs, body: await r.text()};
        }""")
        
        print(f"Login: {login['status']}", flush=True)
        print(f"  Body: {login.get('body', '')[:300]}", flush=True)
        
        if login["status"] == 200:
            print("\n*** LOGIN SUCCESS! ***", flush=True)
        else:
            new_chall = login.get("headers", {}).get("rblx-challenge-id", "")
            if new_chall:
                print(f"  New challenge: {new_chall}", flush=True)
    
    time.sleep(5)
    browser.close()
