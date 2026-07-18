"""Download full Challenge.js and analyze for proofofwork logic."""
import os, time, json, base64, re

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
    
    challenge_data = [None]
    
    def capture_challenge(response):
        url = response.url
        if 'Challenge.js' in url:
            try:
                challenge_data[0] = response.text()
                print(f"[+] Downloaded Challenge.js: {len(challenge_data[0])} bytes", flush=True)
            except Exception as e:
                print(f"[-] Error: {e}", flush=True)
    
    page.on("response", capture_challenge)
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="networkidle")
    time.sleep(5)
    
    challenge_js_body = challenge_data[0]
    if challenge_js_body:
        # Search for proofofwork patterns
        patterns = [
            'proofofwork', 'proof_of_work', 'proofOfWork', 'pow',
            'challengeType', 'eligibleMethods', 'genericChallengeId',
            'arkose', 'funcaptcha', 'enforcement',
            'sessionId', 'redemptionToken',
            'rblx-challenge', 'rblx_challenge',
        ]
        
        print(f"\nSearching Challenge.js ({len(challenge_js_body)} bytes):", flush=True)
        for pat in patterns:
            idx = challenge_js_body.find(pat)
            if idx >= 0:
                ctx = challenge_js_body[max(0, idx-100):idx+200]
                print(f"\n[+] '{pat}' found at {idx}:", flush=True)
                print(f"  {ctx[:300]}", flush=True)
                if len(ctx) > 300:
                    print(f"  ... (truncated, full length: {len(ctx)})")
            
            # Also search case-insensitive
            idx_lower = challenge_js_body.lower().find(pat.lower())
            if idx_lower >= 0 and idx_lower != idx:
                ctx = challenge_js_body[max(0, idx_lower-80):idx_lower+150]
                print(f"\n[+] '{pat}' (lowercase) at {idx_lower}:", flush=True)
                print(f"  {ctx[:250]}", flush=True)
        
        # Save for later analysis
        with open("Challenge.js", "w", encoding="utf-8") as f:
            f.write(challenge_js_body)
        print(f"\n[+] Saved Challenge.js", flush=True)
        
        # Check if it mentions PX
        for px_pat in ['PX', 'px-cdn', 'px-cloud', 'PerimeterX', 'perimeterx']:
            if px_pat in challenge_js_body:
                print(f"[!] Challenge.js contains '{px_pat}'!", flush=True)
    
    time.sleep(3)
    browser.close()
