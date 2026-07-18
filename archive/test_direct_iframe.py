"""Directly create enforcement iframe - bypass Arkose API."""
import os, time, json, base64

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
    
    # Track all Arkose responses
    arkose_responses = []
    page.on("response", lambda r: arkose_responses.append((r.url[:200], r.status, r.request.resource_type)) if 'arkoselabs.roblox.com' in r.url else None)
    
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
    
    if chal_meta_b64:
        meta = json.loads(base64.b64decode(chal_meta_b64).decode())
        session_id = meta.get('sessionId')
        challenge_id = meta.get('challengeId', 'generic-challenge')
        
        print(f"[+] Session: {session_id}", flush=True)
        print(f"[+] Challenge: {challenge_id}", flush=True)
        
        # Create enforcement iframe DIRECTLY
        print(f"\n[*] Creating enforcement iframe directly...", flush=True)
        
        # The enforcement URL format used by Roblox
        env_version = "4.4.2"
        env_hash = "504897d1cd342e063d4f67d90600cf04"
        pk = "476068BF-9607-4799-B53D-966BE98E2B81"
        
        enforce_url = f"https://arkoselabs.roblox.com/v2/{env_version}/enforcement.{env_hash}.html#{pk}&{session_id}"
        
        print(f"  Enforcement URL: {enforce_url[:200]}", flush=True)
        
        # Create iframe in arkose-0 or at document root
        result = page.evaluate("""(url) => {
            const r = {};
            
            // Method 1: Append to arkose-0
            let arkose = document.getElementById('arkose-0');
            if (arkose) {
                const iframe = document.createElement('iframe');
                iframe.src = url;
                iframe.style.width = '100%';
                iframe.style.height = '300px';
                iframe.style.border = 'none';
                iframe.id = 'arkose-enforcement-iframe';
                arkose.appendChild(iframe);
                r.method = 'arkose-0';
            } else {
                // Method 2: Create at document root
                const iframe = document.createElement('iframe');
                iframe.src = url;
                iframe.style.width = '100%';
                iframe.style.height = '300px';
                iframe.style.border = 'none';
                iframe.id = 'arkose-enforcement-iframe';
                document.body.appendChild(iframe);
                r.method = 'body';
            }
            
            r.iframeSet = true;
            r.url = url.substring(0, 200);
            return r;
        }""", enforce_url)
        print(f"  Result: {json.dumps(result)}", flush=True)
        
        # Wait for enforcement page to load
        print("\n[*] Waiting for enforcement iframe (15s)...", flush=True)
        enf_frame = None
        for i in range(30):
            for f in page.frames:
                if 'arkoselabs' in f.url and 'enforcement.' in f.url:
                    enf_frame = f
                    print(f"[+] Enforcement frame at {i*0.5:.0f}s!", flush=True)
                    break
            if enf_frame:
                break
            time.sleep(0.5)
        
        if enf_frame:
            print(f"  URL: {enf_frame.url[:200]}", flush=True)
            enf_frame.screenshot(path="direct_enf.png")
            
            # Check enforcement content
            enf_content = enf_frame.evaluate("""() => ({
                bodyLen: document.body?.innerHTML?.length || 0,
                appHTML: document.getElementById('app')?.innerHTML?.substring(0, 300) || 'empty',
                iframes: Array.from(document.querySelectorAll('iframe')).map(f => f.src).filter(Boolean).slice(0, 5)
            })""")
            print(f"\n  Enforcement content: {json.dumps(enf_content, indent=2)[:1000]}", flush=True)
            
            # Wait for game-core
            print("\n[*] Waiting for game-core (30s)...", flush=True)
            gc_frame = None
            for i in range(60):
                for f in enf_frame.child_frames:
                    if 'game-core' in f.url:
                        gc_frame = f
                        print(f"[+] Game-core at {i*0.5:.0f}s!", flush=True)
                        break
                if gc_frame:
                    break
                time.sleep(0.5)
            
            if gc_frame:
                gc_frame.screenshot(path="direct_gc.png")
                
                # Wait for captcha
                for i in range(20):
                    gc_state = gc_frame.evaluate("""() => ({
                        canvases: document.querySelectorAll('canvas').length,
                        images: document.querySelectorAll('img').length,
                        bodyLen: document.body?.innerHTML?.length || 0
                    })""")
                    if gc_state.get('canvases', 0) > 0 or gc_state.get('images', 0) > 3:
                        print(f"[+] Captcha rendered at {i}s!\n  {json.dumps(gc_state)}", flush=True)
                        gc_frame.screenshot(path="direct_captcha.png")
                        break
                    time.sleep(1)
                else:
                    print(f"[-] No captcha. State: {json.dumps(gc_state)}", flush=True)
            else:
                print(f"[-] No game-core frame. Child frames: {[(f.url[:100], f.name) for f in enf_frame.child_frames]}", flush=True)
        else:
            print(f"[-] No enforcement frame. Current frames: {[(f.url[:100], f.name) for f in page.frames]}", flush=True)
    
    print(f"\n=== Arkose responses ({len(arkose_responses)}) ===", flush=True)
    for url, status, rtype in arkose_responses:
        print(f"  [{status}] {rtype:12s} {url}", flush=True)
    
    page.screenshot(path="direct_final.png")
    
    time.sleep(10)
    browser.close()
