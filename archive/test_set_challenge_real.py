"""Pass real challenge metadata to PX.setChallenge to trigger enforcement."""
import os, time, json, base64

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
    
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        resp = response_info.value
        print(f"[+] Auth: {resp.status}", flush=True)
        
        headers = dict(resp.headers)
        chal_meta_b64 = headers.get('rblx-challenge-metadata', '')
        chal_id = headers.get('rblx-challenge-id', '')
        chal_type = headers.get('rblx-challenge-type', '')
        
        print(f"[+] Challenge type: {chal_type}", flush=True)
        print(f"[+] Challenge ID: {chal_id}", flush=True)
        
        if chal_meta_b64:
            pad = len(chal_meta_b64) % 4
            if pad:
                chal_meta_b64 += '=' * (4 - pad)
            meta = json.loads(base64.b64decode(chal_meta_b64))
            print(f"[+] sessionId: {meta.get('sessionId','')[:30]}...", flush=True)
            sp = meta.get('sharedParameters', {})
            print(f"[+] eligibleMethods: {sp.get('eligibleMethods', 'N/A')}", flush=True)
            
            # Try calling PX.setChallenge with the REAL challenge data
            result = page.evaluate(f"""() => {{
                try {{
                    window.PX.setChallenge({{
                        challengeId: '{chal_id}',
                        metadata: '{chal_meta_b64}'
                    }});
                    return 'setChallenge called';
                }} catch(e) {{
                    return 'setChallenge error: ' + e.message;
                }}
            }}""")
            print(f"[*] {result}", flush=True)
            
            time.sleep(5)
            
            # Check for new frames
            frames = page.frames
            arkose_frames = [f for f in frames if 'arkose' in f.url or 'game-core' in f.url or 'funcaptcha' in f.url]
            enforcement_frames = [f for f in frames if 'enforcement' in f.url]
            print(f"[*] Frames: {len(frames)}, arkose: {len(arkose_frames)}, enforcement: {len(enforcement_frames)}", flush=True)
            for f in frames:
                url_lower = f.url.lower()
                if 'arkose' in url_lower or 'enforcement' in url_lower or 'challenge' in url_lower or 'game-core' in url_lower:
                    print(f"  *** {f.url}", flush=True)
            
            # Also try PX.getEnforcement
            has_get = page.evaluate("typeof window.PX?.getEnforcement === 'function'")
            print(f"[*] PX.getEnforcement exists: {has_get}", flush=True)
            
            if has_get:
                try:
                    enc_result = page.evaluate(f"""() => {{
                        try {{
                            window.PX.getEnforcement('{chal_id}');
                            return 'getEnforcement called';
                        }} catch(e) {{
                            return 'getEnforcement error: ' + e.message;
                        }}
                    }}""")
                    print(f"[*] {enc_result}", flush=True)
                    time.sleep(3)
                    
                    # Check frames again
                    frames2 = page.frames
                    arkose2 = [f for f in frames2 if 'arkose' in f.url or 'game-core' in f.url]
                    print(f"[*] After getEnforcement: arkose={len(arkose2)}", flush=True)
                    for f in frames2:
                        if 'arkose' in f.url.lower() or 'game-core' in f.url.lower():
                            print(f"  *** {f.url}", flush=True)
                except Exception as e:
                    print(f"[-] getEnforcement error: {e}", flush=True)
        
    except Exception as e:
        print(f"[-] No auth: {e}", flush=True)
    
    page.screenshot(path="set_challenge_real.png")
    time.sleep(10)
    browser.close()
