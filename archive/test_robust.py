"""Use working pattern from test_full_captcha - just wait longer."""
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
    
    arkose_urls = []
    page.on("response", lambda r: arkose_urls.append(r.url) if 'arkoselabs.roblox.com' in r.url else None)
    
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
    
    # Wait for arkose container
    for i in range(15):
        if page.evaluate("document.getElementById('arkose-0') ? true : false"):
            print(f"[+] arkose-0 at {i}s", flush=True)
            break
        time.sleep(0.5)
    
    # Trigger enforcement
    if chal_meta_b64:
        original_meta = json.loads(base64.b64decode(chal_meta_b64).decode())
        modified_meta = original_meta.copy()
        if 'sharedParameters' in modified_meta:
            modified_meta['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
            modified_meta['sharedParameters']['renderNativeChallenge'] = True
        new_meta_b64 = base64.b64encode(json.dumps(modified_meta).encode()).decode()
        chal_id = original_meta.get('challengeId', 'generic-challenge')
        chal_type = original_meta.get('challengeType', 'proofofwork')
        
        print(f"[*] Triggering enforcement with captcha method...", flush=True)
        page.evaluate("""(args) => {
            const script = document.createElement('script');
            script.setAttribute('data-rblx-challenge', args.chalId);
            script.setAttribute('data-rblx-challenge-type', args.chalType);
            script.setAttribute('data-rblx-challenge-metadata', args.metaB64);
            document.head.appendChild(script);
            if (typeof window.PX?.setChallenge === 'function') {
                window.PX.setChallenge(JSON.parse(atob(args.metaB64)));
            }
        }""", {'metaB64': new_meta_b64, 'chalId': chal_id, 'chalType': chal_type})
    
    # Wait for enforcement frame - up to 60 seconds
    print("[*] Waiting for enforcement frame (60s)...", flush=True)
    enf_frame = None
    for i in range(120):
        for f in page.frames:
            if 'arkoselabs' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                break
        if enf_frame:
            print(f"[+] Enforcement frame at {i*0.5:.0f}s!", flush=True)
            print(f"  URL: {enf_frame.url[:200]}", flush=True)
            break
        time.sleep(0.5)
    else:
        print(f"[-] No enforcement frame after 60s", flush=True)
        print(f"  Frames ({len(page.frames)}):", flush=True)
        for fi, f in enumerate(page.frames):
            print(f"  [{fi}] {f.url[:120]}", flush=True)
    
    if enf_frame:
        enf_frame.screenshot(path="enforcement.png")
        
        # Wait for game-core inside enforcement
        print("[*] Waiting for game-core in enforcement (30s)...", flush=True)
        gc_frame = None
        for i in range(60):
            for f in enf_frame.child_frames:
                if 'game-core' in f.url:
                    gc_frame = f
                    break
            if gc_frame:
                print(f"[+] Game-core at {i*0.5:.0f}s!", flush=True)
                print(f"  URL: {gc_frame.url[:200]}", flush=True)
                break
            time.sleep(0.5)
        
        if gc_frame:
            gc_frame.screenshot(path="game_core.png")
            
            # Wait for captcha game
            print("[*] Waiting for captcha game (20s)...", flush=True)
            for i in range(20):
                gc_state = gc_frame.evaluate("""() => {
                    const canvases = document.querySelectorAll('canvas');
                    const images = document.querySelectorAll('img');
                    return {
                        canvases: canvases.length,
                        images: images.length,
                        bodyLen: document.body?.innerHTML?.length || 0
                    };
                }""")
                if gc_state.get('canvases', 0) > 0 or gc_state.get('images', 0) > 3:
                    print(f"[+] Captcha game found at {i}s!", flush=True)
                    print(f"  State: {json.dumps(gc_state)}", flush=True)
                    gc_frame.screenshot(path="captcha_game.png")
                    break
                time.sleep(1)
            else:
                print(f"[-] No captcha after 20s. State: {json.dumps(gc_state)}", flush=True)
        else:
            print("[-] No game-core frame found")
    
    print(f"\n=== Arkose URLs ({len(arkose_urls)}) ===", flush=True)
    for u in arkose_urls:
        print(f"  {u[:150]}", flush=True)
    
    page.screenshot(path="final.png")
    
    time.sleep(10)
    browser.close()
