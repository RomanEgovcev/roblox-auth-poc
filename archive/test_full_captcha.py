"""Full flow: trigger enforcement, find game-core, capture captcha."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    
    # Track Arkose URLs
    gc_urls = []
    
    def track_resp(response):
        url = response.url
        if 'game-core/index.html' in url:
            gc_urls.append(url)
            print(f"[GC] URL: {url[:200]}", flush=True)
    
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
    
    # Wait for arkose0 container
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
    
    # Wait for game-core
    print("[*] Waiting for game-core...", flush=True)
    for i in range(30):
        if gc_urls:
            print(f"[+] Game-core URL captured at {i}s!", flush=True)
            break
        if i == 10:
            print("[*] Still waiting for game-core...", flush=True)
        time.sleep(1)
    
    # Take full page screenshot
    page.screenshot(path="captcha_full.png")
    
    # Check frames
    print(f"\n[*] Frames ({len(page.frames)}):", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:150]}", flush=True)
    
    # Check DOM state
    dom = page.evaluate("""() => ({
        arkose0_children: document.getElementById('arkose-0')?.childElementCount || 0,
        arkose0_html: document.getElementById('arkose-0')?.innerHTML?.substring(0, 200) || '',
        arkoseIframes: document.querySelectorAll('#arkose-0 iframe').length,
        scripts: Array.from(document.querySelectorAll('script[id^=arkose-script]')).map(s => ({
            id: s.id, src: (s.src || '').substring(0, 150)
        }))
    })""")
    print(f"\n=== DOM ===", flush=True)
    print(json.dumps(dom, indent=2)[:1500], flush=True)
    
    # If game-core URL found, load it directly
    if gc_urls:
        gc_url = gc_urls[-1]
        print(f"\n[*] Loading game-core directly...", flush=True)
        gc_page = browser.new_page()
        gc_page.goto(gc_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)
        gc_page.screenshot(path="game_core_loaded.png")
        
        # Check for captcha elements
        for i in range(15):
            gc_state = gc_page.evaluate("""() => {
                const canvases = document.querySelectorAll('canvas');
                const images = document.querySelectorAll('img');
                const buttons = document.querySelectorAll('button');
                const bodyLen = document.body?.innerHTML?.length || 0;
                return {
                    canvases: canvases.length,
                    images: images.length,
                    buttons: buttons.length,
                    bodyLen: bodyLen,
                    bodyPreview: document.body?.innerHTML?.substring(0, 500) || ''
                };
            }""")
            if gc_state.get('canvases', 0) > 0 or gc_state.get('images', 0) > 2:
                print(f"[+] Captcha elements found at {i}s!", flush=True)
                print(f"  State: {json.dumps(gc_state)[:500]}", flush=True)
                gc_page.screenshot(path=f"captcha_game.png")
                break
            time.sleep(1)
        else:
            print(f"[-] No captcha after 15s. State: {json.dumps(gc_state)[:500]}", flush=True)
            # Try checking frames in gc_page
            print(f"  GC Frames: {[(f.url[:100], f.name) for f in gc_page.frames]}", flush=True)
        
        time.sleep(10)
    
    browser.close()
