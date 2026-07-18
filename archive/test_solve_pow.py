"""Solve proofofwork challenge and complete login."""
import os, time, json, base64, hashlib

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

def find_proof(prefix, difficulty=4):
    """Hashcash-style PoW: find nonce where SHA256(prefix+nonce) starts with `difficulty` zero hex chars."""
    nonce = 0
    target = '0' * difficulty
    while True:
        h = hashlib.sha256(f"{prefix}{nonce}".encode()).hexdigest()
        if h.startswith(target):
            return str(nonce), h
        nonce += 1
        if nonce > 1000000:
            return None, None

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Step 1: Get CSRF token
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF: {csrf}", flush=True)
    
    # Step 2: Login with CSRF to get challenge
    chall = page.evaluate(f"""() => {{
        return new Promise((resolve) => {{
            const xhr = new XMLHttpRequest();
            xhr.open('POST', 'https://auth.roblox.com/v2/login', true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.setRequestHeader('x-csrf-token', '{csrf}');
            xhr.withCredentials = true;
            xhr.onload = function() {{
                const headers = {{}};
                xhr.getAllResponseHeaders().trim().split('\\n').forEach(h => {{
                    const [k, ...v] = h.split(':');
                    if (k && v.length) headers[k.trim().toLowerCase()] = v.join(':').trim();
                }});
                resolve({{status: xhr.status, headers: headers}});
            }};
            xhr.onerror = () => resolve({{error: 'XHR failed'}});
            xhr.send(JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}));
        }});
    }}""")
    
    if chall.get('error'):
        print(f"Error: {chall['error']}", flush=True)
        browser.close()
        exit()
    
    print(f"\nLogin response: {chall['status']}", flush=True)
    h = chall.get('headers', {})
    chall_id = h.get('rblx-challenge-id', '')
    chall_type = h.get('rblx-challenge-type', '')
    chall_meta_b64 = h.get('rblx-challenge-metadata', '')
    
    if not chall_id:
        print("No challenge! Login might have succeeded?", flush=True)
        print(f"Headers: {json.dumps(h, indent=2)}", flush=True)
        browser.close()
        exit()
    
    print(f"Challenge: {chall_id} ({chall_type})", flush=True)
    
    # Decode metadata
    meta = json.loads(base64.b64decode(chall_meta_b64 + '==').decode())
    session_id = meta.get('sessionId', '')
    generic_id = meta.get('sharedParameters', {}).get('genericChallengeId', '')
    eligible = meta.get('sharedParameters', {}).get('eligibleMethods', [])
    print(f"sessionId: {session_id}", flush=True)
    print(f"genericChallengeId: {generic_id}", flush=True)
    print(f"eligibleMethods: {eligible}", flush=True)
    
    # If eligibleMethods includes funcaptcha, we'd need a solver
    # If it's proofofwork with no eligible methods, try computing a proof
    
    # Try various proof values
    proofs_to_try = [
        session_id,
        generic_id,
        chall_id,
        hashlib.sha256(session_id.encode()).hexdigest(),
        hashlib.md5(session_id.encode()).hexdigest(),
    ]
    
    # Also try hashcash with different prefixes
    for prefix in [session_id, generic_id, chall_id]:
        for difficulty in range(1, 5):
            proof, h = find_proof(prefix, difficulty)
            if proof:
                proofs_to_try.append(proof)
                break
    
    print(f"\nTrying {len(proofs_to_try)} proofs...", flush=True)
    
    for proof in proofs_to_try:
        # Get fresh CSRF
        csrf2 = page.evaluate(f"""() => {{
            return fetch('https://auth.roblox.com/v2/login', {{
                method: 'POST', credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
            }}).then(r => r.headers.get('x-csrf-token'));
        }}""")
        
        # Try POST challenge solution
        result = page.evaluate(f"""() => {{
            return new Promise((resolve) => {{
                const xhr = new XMLHttpRequest();
                xhr.open('POST', 'https://auth.roblox.com/v2/login', true);
                xhr.setRequestHeader('Content-Type', 'application/json');
                xhr.setRequestHeader('x-csrf-token', '{csrf2}');
                xhr.setRequestHeader('rblx-challenge-id', '{chall_id}');
                xhr.setRequestHeader('rblx-challenge-type', '{chall_type}');
                xhr.setRequestHeader('rblx-challenge-solution', '{proof}');
                xhr.withCredentials = true;
                xhr.onload = function() {{
                    const hdrs = {{}};
                    xhr.getAllResponseHeaders().trim().split('\\n').forEach(h => {{
                        const [k, ...v] = h.split(':');
                        if (k && v.length) hdrs[k.trim().toLowerCase()] = v.join(':').trim();
                    }});
                    resolve({{status: xhr.status, headers: hdrs, body: xhr.responseText.substring(0, 200)}});
                }};
                xhr.onerror = () => resolve({{error: 'XHR failed'}});
                xhr.send(JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}));
            }});
        }}""")
        
        if result.get('error'):
            print(f"  XHR error for proof '{proof[:20]}...'", flush=True)
            continue
        
        status = result['status']
        body = result.get('body', '')
        
        if status == 200:
            print(f"\n*** LOGIN SUCCESS! proof='{proof[:20]}...' ***", flush=True)
            print(f"  Body: {body}", flush=True)
            break
        elif status == 403 and 'Challenge' in body:
            # Still challenged - try different proof
            new_chall = result.get('headers', {}).get('rblx-challenge-id', '')
            new_type = result.get('headers', {}).get('rblx-challenge-type', '')
            if new_chall:
                print(f"  New challenge: {new_chall} ({new_type})", flush=True)
                # Update challenge if it changed
                chall_id = new_chall
                chall_type = new_type
            else:
                print(f"  Proof '{proof[:20]}...' -> {status}: {body[:80]}", flush=True)
        else:
            print(f"  Proof '{proof[:20]}...' -> {status}: {body[:80]}", flush=True)
    
    time.sleep(2)
    browser.close()
