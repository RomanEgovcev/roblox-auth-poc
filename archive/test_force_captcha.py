"""Force captcha by modifying auth 403 response headers/metadata."""
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
    
    # Intercept auth response to add captcha headers
    def intercept(route):
        url = route.request.url
        
        # Patch PX script
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
            return
        
        # Intercept auth 403 and modify response
        if 'auth.roblox.com' in url and '/v2/login' in url:
            original_response = route.request.response()
            
            # Let the response go through first, then fulfill with modified version
            route.continue_()
            return
        
        route.continue_()
    
    page.route("**/*", intercept)
    
    # Actually, let's use response interception instead
    # We need to intercept BEFORE the response is sent to the page
    # Let me use a simpler approach
    
    browser.close()
    
    # ===== RESTART WITH PROPER APPROACH =====
    
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    arkose_resp = []
    def track_resp(response):
        url = response.url
        if 'arkoselabs.roblox.com' in url:
            arkose_resp.append(f"[{response.status}] {url[:180]}")
    page.on("response", track_resp)
    
    def intercept(route):
        url = route.request.url
        
        # Patch PX script
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
            return
        
        # For auth login: let it go, we'll modify via continue_
        route.continue_()
    
    page.route("**/*", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # ===== KEY: intercept auth response and modify =====
    # We need to modify the auth 403 BEFORE the page processes it
    # Use route.fulfill to replace the response entirely
    
    print("[*] Setting up auth response modification...", flush=True)
    
    # Remove old route and set up auth interceptor
    page.unroute("**/*")
    
    modified_meta_for_trigger = None
    
    def intercept_with_mod(route):
        url = route.request.url
        nonlocal modified_meta_for_trigger
        
        # Patch PX script
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
            return
        
        # Intercept auth 403
        if 'auth.roblox.com' in url and '/v2/login' in url:
            # Continue to get the response
            route.continue_()
            return
        
        route.continue_()
    
    page.route("**/*", intercept_with_mod)
    
    # Now click and handle the auth response via the response event
    print("[*] Clicking login...", flush=True)
    
    chal_meta_b64 = None
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        resp = response_info.value
        print(f"[+] Auth: {resp.status}", flush=True)
        
        # Get original metadata
        for k, v in resp.headers.items():
            if k.lower() == 'rblx-challenge-metadata':
                chal_meta_b64 = v
                break
        
        if chal_meta_b64:
            original_meta = json.loads(base64.b64decode(chal_meta_b64).decode())
            print(f"  Original eligibleMethods: {original_meta.get('sharedParameters',{}).get('eligibleMethods')}", flush=True)
            
            # Now MODIFY the response via route.fulfill
            # Get the response body
            body = resp.body()
            
            # Modify metadata to include captcha
            modified_meta = original_meta.copy()
            if 'sharedParameters' in modified_meta:
                modified_meta['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
                modified_meta['sharedParameters']['renderNativeChallenge'] = True
            modified_meta_b64 = base64.b64encode(json.dumps(modified_meta).encode()).decode()
            
            print(f"  Modified eligibleMethods: {modified_meta.get('sharedParameters',{}).get('eligibleMethods')}", flush=True)
            print(f"  Modified renderNativeChallenge: {modified_meta.get('sharedParameters',{}).get('renderNativeChallenge')}", flush=True)
            
            modified_meta_for_trigger = modified_meta
            
            # We need to re-send the modified response
            modified_headers = dict(resp.headers)
            modified_headers['rblx-challenge-type'] = 'captcha'
            modified_headers['rblx-challenge-metadata'] = modified_meta_b64
            
            # Fulfill the response again with modified headers
            # But route.fulfill can only be called once...
            # This approach doesn't work well. Let me intercept BEFORE.
            
            print(f"\n[*] Creating script tag with modified metadata...", flush=True)
            
            # Use the manual trigger approach instead
            new_meta_b64 = modified_meta_b64
            chal_id = original_meta.get('challengeId', 'generic-challenge')
            chal_type = 'captcha'  # Force captcha type
            
            page.evaluate("""(args) => {
                const script = document.createElement('script');
                script.setAttribute('data-rblx-challenge', args.chalId);
                script.setAttribute('data-rblx-challenge-type', args.chalType);
                script.setAttribute('data-rblx-challenge-metadata', args.metaB64);
                document.head.appendChild(script);
                if (typeof window.PX?.setChallenge === 'function') {
                    try { window.PX.setChallenge(JSON.parse(atob(args.metaB64))); }
                    catch(e) { console.error('PX.setChallenge error:', e); }
                }
            }""", {'metaB64': new_meta_b64, 'chalId': chal_id, 'chalType': chal_type})
            
            # ===== WAIT for Arkose activity =====
            print("[*] Waiting for Arkose activity (30s)...", flush=True)
            for i in range(60):
                new_r = [r for r in arkose_resp if not r.startswith('_')]
                for r in new_r:
                    print(f"  {r}", flush=True)
                
                if i % 10 == 0 and i > 0:
                    dom = page.evaluate("""() => ({
                        arkose0: document.getElementById('arkose-0') ? 'exists' : 'missing',
                        scripts: document.querySelectorAll('script[id^=arkose-script]').length,
                        iframes: document.querySelectorAll('#arkose-0 iframe').length,
                    })""")
                    print(f"  [{i*0.5:.0f}s] DOM: {json.dumps(dom)}", flush=True)
                
                time.sleep(0.5)
            
            # ===== Also try direct enforcement iframe =====
            print(f"\n[*] Creating direct enforcement iframe...", flush=True)
            
            # Use sessionId from original metadata as session token
            session_id = original_meta.get('sessionId', '')
            enforce_url = f"https://arkoselabs.roblox.com/v2/4.4.2/enforcement.504897d1cd342e063d4f67d90600cf04.html#476068BF-9607-4799-B53D-966BE98E2B81&{session_id}"
            
            page.evaluate("""(url) => {
                const div = document.createElement('div');
                div.id = 'arkose-1';
                div.style.width = '600px'; div.style.height = '500px';
                div.style.border = '2px solid blue';
                document.body.appendChild(div);
                const iframe = document.createElement('iframe');
                iframe.src = url;
                iframe.style.width = '100%'; iframe.style.height = '100%';
                div.appendChild(iframe);
            }""", enforce_url)
            
            # Wait for enforcement frame
            print("[*] Waiting for enforcement frame (60s)...", flush=True)
            enf_frame = None
            for i in range(120):
                for f in page.frames:
                    if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                        enf_frame = f
                        break
                if enf_frame:
                    print(f"[+] Enforcement frame at {i*0.5:.0f}s!", flush=True)
                    break
                if i % 20 == 0 and i > 0:
                    print(f"  [{i*0.5:.0f}s] frames={len(page.frames)}", flush=True)
                time.sleep(0.5)
            
            if enf_frame:
                # Wait for game-core
                print("[*] Waiting for game-core in enforcement (60s)...", flush=True)
                for i in range(120):
                    try:
                        state = enf_frame.evaluate("""() => ({
                            challenge: !!document.getElementById('challenge'),
                            funCaptcha: !!document.getElementById('FunCaptcha'),
                            appHTML: document.getElementById('app')?.innerHTML?.substring(0, 200) || 'N/A',
                        })""")
                        if state['challenge'] or state['funCaptcha']:
                            print(f"[+] Challenge at {i*0.5:.0f}s!", flush=True)
                            try: enf_frame.screenshot(path="enf_captcha.png")
                            except: pass
                            break
                    except:
                        pass
                    if i % 30 == 0 and i > 0:
                        print(f"  [{i*0.5:.0f}s] {json.dumps(state)[:200]}", flush=True)
                    time.sleep(0.5)
    
    except Exception as e:
        print(f"[-] Error: {e}", import traceback; traceback.print_exc())
    
    print(f"\n=== Arkose responses: {len(arkose_resp)} ===", flush=True)
    for r in arkose_resp:
        print(f"  {r}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:150]}", flush=True)
    
    page.screenshot(path="final_forced_captcha.png")
    time.sleep(10)
    browser.close()
