"""Try multiple proof values for proofofwork challenge."""
import os, time, json, base64, hashlib

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    challenge_info = {}
    page.on("response", lambda r: challenge_info.update({
        "id": r.headers.get('rblx-challenge-id', ''),
        "type": r.headers.get('rblx-challenge-type', ''),
        "meta": r.headers.get('rblx-challenge-metadata', ''),
    }) if '/v2/login' in r.url and r.headers.get('rblx-challenge-id') else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF: {csrf}", flush=True)
    
    page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }});
    }}""")
    time.sleep(2)
    
    chall_id = challenge_info.get('id', '')
    chall_type = challenge_info.get('type', '')
    chall_meta_b64 = challenge_info.get('meta', '')
    
    if not chall_id:
        print("No challenge!", flush=True)
        browser.close()
        exit()
    
    meta = json.loads(base64.b64decode(chall_meta_b64 + '==').decode())
    session_id = meta.get('sessionId', '')
    generic_id = meta.get('sharedParameters', {}).get('genericChallengeId', '')
    
    print(f"Challenge: {chall_id} ({chall_type})", flush=True)
    print(f"sessionId: {session_id}", flush=True)
    print(f"genericId: {generic_id}", flush=True)
    
    # Generate candidate proofs
    candidates = []
    
    # Basic values
    candidates.append(("chall_id", chall_id))
    candidates.append(("session_id", session_id))
    candidates.append(("generic_id", generic_id))
    
    # Last segment of UUID
    candidates.append(("chall_uuid_last", chall_id.split('-')[-1]))
    candidates.append(("session_uuid_last", session_id.split('-')[-1]))
    
    # SHA256 hashes
    candidates.append(("sha256(session)", hashlib.sha256(session_id.encode()).hexdigest()))
    candidates.append(("sha256(chall)", hashlib.sha256(chall_id.encode()).hexdigest()))
    candidates.append(("md5(session)", hashlib.md5(session_id.encode()).hexdigest()))
    
    # Hashcash: find nonce for various difficulties
    for prefix in [session_id, chall_id, generic_id]:
        for diff in [1, 2, 3, 4]:
            nonce = 0
            target = '0' * diff
            while nonce < 50000:
                h = hashlib.sha256(f"{prefix}{nonce}".encode()).hexdigest()
                if h.startswith(target):
                    candidates.append((f"hashcash_{prefix[:8]}_diff{diff}", str(nonce)))
                    break
                nonce += 1
    
    # Numeric values
    for n in [1, 2, 3, 5, 10, 100, 1000]:
        candidates.append((f"number_{n}", str(n)))
    
    print(f"\nTrying {len(candidates)} candidates...", flush=True)
    
    def try_solution(proof):
        global csrf
        csrf = page.evaluate(f"""() => {{
            return fetch('https://auth.roblox.com/v2/login', {{
                method: 'POST', credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
            }}).then(r => r.headers.get('x-csrf-token'));
        }}""")
        
        # Route this specific request
        result_holder = [None]
        def route_it(route):
            if route.request.method == 'POST' and '/v2/login' in route.request.url:
                h = dict(route.request.headers)
                if 'x-csrf-token' in h:
                    h['rblx-challenge-id'] = chall_id
                    h['rblx-challenge-type'] = chall_type
                    h['rblx-challenge-solution'] = proof
                route.continue_(headers=h)
            else:
                route.continue_()
        
        page.route("https://auth.roblox.com/v2/login", route_it)
        
        result = page.evaluate(f"""() => {{
            return fetch('https://auth.roblox.com/v2/login', {{
                method: 'POST', credentials: 'include',
                headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
                body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
            }}).then(async r => {{
                return {{status: r.status, body: (await r.text()).substring(0, 100)}};
            }});
        }}""")
        
        page.unroute("https://auth.roblox.com/v2/login", route_it)
        return result
    
    for label, proof in candidates:
        result = try_solution(proof)
        s = result.get('status', '?')
        b = result.get('body', '')
        
        if s == 200:
            print(f"\n*** SUCCESS! proof='{proof[:30]}' ({label}) ***", flush=True)
            print(f"  Body: {b}", flush=True)
            break
        elif 'succeed' in b.lower() or 'success' in b.lower():
            print(f"\n*** POSSIBLE SUCCESS! proof='{proof[:30]}' ({label}) -> {s}: {b}", flush=True)
        elif 'Challenge failed' in b:
            pass  # Expected
        elif s == 403 and 'Challenge' in b:
            pass  # Another challenge issued
        else:
            print(f"  [{label[:20]}] proof='{proof[:20]}' -> {s}: {b[:60]}", flush=True)
    
    print(f"\nDone. Last result: {result.get('status')}: {result.get('body', '')[:60]}", flush=True)
    
    time.sleep(2)
    browser.close()
