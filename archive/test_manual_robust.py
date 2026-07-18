"""Robust manual trigger with long waits."""
import os, time, json, base64, sys

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script.replace('new Function("return this")()', "(window||self||globalThis)")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    arkose_urls = []
    def track_resp(response):
        url = response.url
        if 'arkoselabs.roblox.com' in url or 'game-core' in url:
            t = response.request.resource_type
            arkose_urls.append(f"[{response.status}] {t} {url[:180]}")
            if 'game-core/index.html' in url:
                print(f"\n[GAME-CORE RESPONSE] at {len(arkose_urls)}!", flush=True)
    page.on("response", track_resp)
    
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
    
    chal_meta_b64 = None
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        resp = response_info.value
        for k, v in resp.headers.items():
            if k.lower() == 'rblx-challenge-metadata':
                chal_meta_b64 = v
                break
        print(f"[+] Auth: {resp.status}", flush=True)
    except Exception as e:
        print(f"[-] Auth: {e}", flush=True)
        browser.close()
        sys.exit(1)
    
    if not chal_meta_b64:
        print("[-] No challenge metadata!", flush=True)
        browser.close()
        sys.exit(1)
    
    original_meta = json.loads(base64.b64decode(chal_meta_b64).decode())
    print(f"[+] Meta: sessionId={original_meta.get('sessionId','?')[:20]}", flush=True)
    
    # ===== MANUAL TRIGGER with MODIFIED metadata =====
    modified_meta = original_meta.copy()
    if 'sharedParameters' in modified_meta:
        modified_meta['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
        modified_meta['sharedParameters']['renderNativeChallenge'] = True
    new_meta_b64 = base64.b64encode(json.dumps(modified_meta).encode()).decode()
    chal_id = original_meta.get('challengeId', 'generic-challenge')
    chal_type = original_meta.get('challengeType', 'proofofwork')
    
    print(f"\n[*] Triggering enforcement with modified metadata...", flush=True)
    
    result = page.evaluate("""(args) => {
        const r = {};
        r.PX_exists = typeof window.PX !== 'undefined';
        r.PX_setChallenge = typeof window.PX?.setChallenge;
        r.oC_before = typeof window.oC;
        r.ph_before = window.ph;
        
        // Method 1: Create script[data-rblx-challenge]
        const script = document.createElement('script');
        script.setAttribute('data-rblx-challenge', args.chalId);
        script.setAttribute('data-rblx-challenge-type', args.chalType);
        script.setAttribute('data-rblx-challenge-metadata', args.metaB64);
        document.head.appendChild(script);
        r.scriptAdded = true;
        
        // Method 2: Call PX.setChallenge
        if (typeof window.PX?.setChallenge === 'function') {
            try {
                const chalData = JSON.parse(atob(args.metaB64));
                window.PX.setChallenge(chalData);
                r.setChallengeCalled = true;
            } catch(e) { r.setChallengeError = e.message; }
        }
        
        r.oC_after = typeof window.oC;
        r.ph_after = window.ph;
        
        return r;
    }""", {'metaB64': new_meta_b64, 'chalId': chal_id, 'chalType': chal_type})
    print(f"  Trigger result: {json.dumps(result)}", flush=True)
    
    # ===== WAIT for enforcement iframe (LONG) =====
    print("\n[*] Waiting for enforcement iframe (up to 90s)...", flush=True)
    enf_frame = None
    for i in range(180):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                break
        if enf_frame:
            print(f"[+] Enforcement frame at {i*0.5:.0f}s!", flush=True)
            break
        if i % 20 == 0 and i > 0:
            print(f"  [{int(i*0.5)}s] Still waiting... frames={len(page.frames)} ", flush=True)
        time.sleep(0.5)
    
    if not enf_frame:
        print("[-] No enforcement iframe after 90s!", flush=True)
        print(f"\nFinal frames: {[(f.url[:100]) for f in page.frames]}", flush=True)
        
        # Check DOM for arkose containers
        dom = page.evaluate("""() => ({
            arkose0: document.getElementById('arkose-0')?.innerHTML?.substring(0, 200) || 'missing',
            arkoseScripts: Array.from(document.querySelectorAll('script[id^=arkose-script]')).map(s => s.src.substring(0, 120))
        })""")
        print(f"DOM: {json.dumps(dom)[:500]}", flush=True)
        
        browser.close()
        sys.exit(1)
    
    # ===== WAIT for challenge within enforcement =====
    print("\n[*] Waiting for challenge/game-core in enforcement frame (up to 90s)...", flush=True)
    game_core = False
    for i in range(180):
        try:
            has_challenge = enf_frame.evaluate("""() => {
                return {
                    challenge: !!document.getElementById('challenge'),
                    funCaptcha: !!document.getElementById('FunCaptcha'),
                    iframes: Array.from(document.querySelectorAll('iframe')).map(f => f.src).filter(Boolean).length,
                    appHTML: document.getElementById('app')?.innerHTML?.substring(0, 100) || ''
                };
            }""")
            
            if has_challenge.get('challenge') or has_challenge.get('funCaptcha') or has_challenge.get('iframes', 0) > 0:
                game_core = True
                print(f"[+] Challenge/game-core found at {i*0.5:.0f}s!", flush=True)
                print(f"  {json.dumps(has_challenge)}", flush=True)
                
                # Take screenshot of enforcement frame
                try:
                    enf_frame.screenshot(path="enf_with_challenge.png")
                    print(f"  Screenshot saved", flush=True)
                except:
                    pass
                break
        except Exception as e:
            if i % 20 == 0:
                print(f"  [{int(i*0.5)}s] Error: {e}", flush=True)
        
        if i % 30 == 0 and i > 0:
            print(f"  [{int(i*0.5)}s] Still waiting...", flush=True)
        time.sleep(0.5)
    
    if not game_core:
        print(f"[-] No challenge after 90s", flush=True)
        # Check enforcement frame state
        try:
            enf_state = enf_frame.evaluate("""() => ({
                bodyLen: document.body?.innerHTML?.length || 0,
                scripts: document.querySelectorAll('script').length,
                appHTML: document.getElementById('app')?.innerHTML?.substring(0, 500) || ''
            })""")
            print(f"  Enforcement state: {json.dumps(enf_state)[:500]}", flush=True)
        except Exception as e:
            print(f"  Error reading enforcement: {e}", flush=True)
    
    # ===== PRINT SUMMARY =====
    print(f"\n=== Arkose network requests ({len(arkose_urls)}) ===", flush=True)
    for u in arkose_urls:
        print(f"  {u}", flush=True)
    
    print(f"\n=== Frames ({len(page.frames)}) ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:150]}", flush=True)
    
    page.screenshot(path="final_manual_robust.png")
    
    time.sleep(10)
    browser.close()
