"""Wait longer for enforcement frame, access game-core."""
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
    
    logs = []
    page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text[:300]}"))
    
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
        
        print(f"[*] Triggering enforcement...", flush=True)
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
    
    # Longer wait for enforcement frame (30s total)
    print("[*] Waiting up to 30s for enforcement frame...", flush=True)
    enf_frame = None
    for i in range(60):
        for f in page.frames:
            if 'arkoselabs' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                print(f"[+] Enforcement frame found at {i*0.5:.0f}s!", flush=True)
                print(f"  URL: {f.url[:200]}", flush=True)
                break
        if enf_frame:
            break
        if i % 20 == 0 and i > 0:
            # Check current frames
            print(f"  Current frames: {[(f.url[:80], f.name[:30]) for f in page.frames]}", flush=True)
        time.sleep(0.5)
    
    if not enf_frame:
        print("[-] Enforcement frame not found after 30s", flush=True)
        print(f"  All frames: {[(f.url[:120], f.name) for f in page.frames]}", flush=True)
    else:
        # Check enforcement content  
        enf_content = enf_frame.evaluate("""() => ({
            bodyLen: document.body?.innerHTML?.length || 0,
            bodyStart: document.body?.innerHTML?.substring(0, 300) || '',
            iframes: Array.from(document.querySelectorAll('iframe')).map(f => f.src).filter(Boolean).slice(0, 5),
            childFrames: window.length  // number of child frames
        })""")
        print(f"\n=== Enforcement content ===", flush=True)
        print(json.dumps(enf_content, indent=2)[:1500], flush=True)
        
        # Wait for game-core
        print("\n[*] Waiting for game-core in enforcement (30s)...", flush=True)
        gc_frame = None
        for i in range(60):
            for f in enf_frame.child_frames:
                if 'game-core' in f.url:
                    gc_frame = f
                    print(f"[+] Game-core found at {i*0.5:.0f}s!", flush=True)
                    print(f"  URL: {f.url[:200]}", flush=True)
                    break
            if gc_frame:
                break
            time.sleep(0.5)
        
        if gc_frame:
            gc_frame.screenshot(path="game_core.png")
            for i in range(20):
                gc_state = gc_frame.evaluate("""() => {
                    const canvases = document.querySelectorAll('canvas');
                    const images = document.querySelectorAll('img');
                    const body = document.body?.innerHTML || '';
                    return {canvases: canvases.length, images: images.length, bodyLen: body.length};
                }""")
                if gc_state.get('canvases', 0) > 0 or gc_state.get('images', 0) > 3:
                    print(f"[+] Captcha rendered at {i}s!\n  {json.dumps(gc_state)}", flush=True)
                    break
                time.sleep(1)
            gc_frame.screenshot(path="captcha_final.png")
        else:
            print("[-] No game-core frame", flush=True)
    
    page.screenshot(path="final_state.png")
    
    print(f"\n=== Logs with 'error' or 'captcha' ===", flush=True)
    for log in logs:
        lower = log.lower()
        if 'error' in lower or 'captcha' in lower or 'arkose' in lower or 'challenge' in lower:
            print(f"  {log[:200]}", flush=True)
    
    time.sleep(5)
    browser.close()
