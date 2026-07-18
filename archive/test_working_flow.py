"""Working approach: manual trigger + long waits + oC (not window.oC)."""
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
    print(f"[+] Meta sessionId={original_meta.get('sessionId','?')[:20]}", flush=True)
    
    # ===== MANUAL TRIGGER =====
    modified_meta = original_meta.copy()
    if 'sharedParameters' in modified_meta:
        modified_meta['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
        # DO NOT set renderNativeChallenge
    new_meta_b64 = base64.b64encode(json.dumps(modified_meta).encode()).decode()
    chal_id = original_meta.get('challengeId', 'generic-challenge')
    chal_type = original_meta.get('challengeType', 'proofofwork')
    
    print(f"\n[*] Triggering enforcement...", flush=True)
    
    page.evaluate("""(args) => {
        const script = document.createElement('script');
        script.setAttribute('data-rblx-challenge', args.chalId);
        script.setAttribute('data-rblx-challenge-type', args.chalType);
        script.setAttribute('data-rblx-challenge-metadata', args.metaB64);
        document.head.appendChild(script);
        
        if (typeof window.PX?.setChallenge === 'function') {
            try {
                window.PX.setChallenge(JSON.parse(atob(args.metaB64)));
            } catch(e) { console.error('PX.setChallenge error:', e); }
        }
    }""", {'metaB64': new_meta_b64, 'chalId': chal_id, 'chalType': chal_type})
    
    # ===== WAIT for arkose scripts (5-10s) =====
    print("[*] Waiting for arkose scripts (up to 15s)...", flush=True)
    arkose_ready = False
    for i in range(30):
        state = page.evaluate("""() => ({
            arkose0: document.getElementById('arkose-0') ? 'exists' : 'missing',
            arkoseScripts: document.querySelectorAll('script[id^=arkose-script]').length,
            iframes: document.querySelectorAll('#arkose-0 iframe').length,
            challengeContainer: document.getElementById('generic-challenge-container-proofofwork') ? 'exists' : 'missing',
            oC: typeof oC !== 'undefined' ? 'set' : 'undefined',
            ph: typeof ph !== 'undefined' ? 'set' : 'undefined',
        })""")
        
        if state['arkoseScripts'] > 0 or state['iframes'] > 0:
            print(f"[+] Arkose activity at {i*0.5:.0f}s: {json.dumps(state)}", flush=True)
            arkose_ready = True
            break
        
        if i % 10 == 0 and i > 0:
            print(f"  [{int(i*0.5)}s] {json.dumps(state)}", flush=True)
        time.sleep(0.5)
    
    if not arkose_ready:
        print(f"[-] No arkose activity after 15s", flush=True)
        # Try direct iframe as fallback
        print("[*] Trying direct iframe fallback...", flush=True)
        enforce_url = f"https://arkoselabs.roblox.com/v2/4.4.2/enforcement.504897d1cd342e063d4f67d90600cf04.html#476068BF-9607-4799-B53D-966BE98E2B81&{original_meta.get('sessionId','')}"
        page.evaluate("""(url) => {
            const div = document.createElement('div');
            div.id = 'arkose-0';
            document.body.appendChild(div);
            const iframe = document.createElement('iframe');
            iframe.src = url;
            div.appendChild(iframe);
        }""", enforce_url)
        
        # Check if enforcement frame appears
        for i in range(60):
            for f in page.frames:
                if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                    arkose_ready = True
                    print(f"[+] Direct iframe enforcement at {i*0.5:.0f}s!", flush=True)
                    break
            if arkose_ready:
                break
            time.sleep(0.5)
    
    # ===== WAIT for enforcement iframe =====
    print("\n[*] Waiting for enforcement iframe (up to 120s)...", flush=True)
    enf_frame = None
    for i in range(240):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                break
        if enf_frame:
            print(f"[+] Enforcement frame at {i*0.5:.0f}s!", flush=True)
            print(f"  URL: {enf_frame.url[:200]}", flush=True)
            break
        if i % 40 == 0 and i > 0:
            print(f"  [{int(i*0.5)}s] Still waiting... frames={len(page.frames)}", flush=True)
        time.sleep(0.5)
    
    if not enf_frame:
        print("[-] No enforcement iframe after 120s!", flush=True)
        print(f"Frames: {[(f.url[:100]) for f in page.frames]}", flush=True)
        page.screenshot(path="no_enf.png")
        browser.close()
        sys.exit(1)
    
    # ===== WAIT for game-core inside enforcement =====
    print("\n[*] Waiting for game-core/challenge inside enforcement (up to 120s)...", flush=True)
    game_ready = False
    for i in range(240):
        try:
            state = enf_frame.evaluate("""() => {
                const app = document.getElementById('app');
                return {
                    appHTML: app ? app.innerHTML.substring(0, 200) : 'missing',
                    challenge: !!document.getElementById('challenge'),
                    funCaptcha: !!document.getElementById('FunCaptcha'),
                    iframes: Array.from(document.querySelectorAll('iframe')).map(f => f.src).filter(Boolean),
                    bodyLen: document.body?.innerHTML?.length || 0,
                    scripts: document.querySelectorAll('script').length,
                };
            }""")
            
            iframes = state.get('iframes', [])
            if state['challenge'] or state['funCaptcha'] or (iframes and len(iframes) > 0):
                print(f"[+] Challenge found at {i*0.5:.0f}s!", flush=True)
                print(f"  {json.dumps({k:v for k,v in state.items() if k in ['challenge','funCaptcha','iframes']})}", flush=True)
                game_ready = True
                try:
                    enf_frame.screenshot(path="enf_game_ready.png")
                except: pass
                break
                
        except Exception as e:
            if i % 40 == 0:
                print(f"  [{int(i*0.5)}s] Error: {e}", flush=True)
        
        if i % 60 == 0 and i > 0:
            print(f"  [{int(i*0.5)}s] Still waiting...", flush=True)
        time.sleep(0.5)
    
    if not game_ready:
        print(f"[-] No challenge after 120s", flush=True)
    
    # ===== SUMMARY =====
    print(f"\n=== Arkose network requests ({len(arkose_urls)}) ===", flush=True)
    for u in arkose_urls:
        print(f"  {u}", flush=True)
    
    print(f"\n=== Frames ({len(page.frames)}) ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:150]}", flush=True)
    
    page.screenshot(path="final_working.png")
    time.sleep(10)
    browser.close()
