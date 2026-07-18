"""FunCaptcha is rendered! Capture game-core and prepare for solving."""
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
        enforce_url = f"https://arkoselabs.roblox.com/v2/4.4.2/enforcement.504897d1cd342e063d4f67d90600cf04.html#476068BF-9607-4799-B53D-966BE98E2B81&{session_id}"
        
        print(f"[*] Creating iframe...", flush=True)
        page.evaluate("""(url) => {
            const iframe = document.createElement('iframe');
            iframe.src = url;
            iframe.style.width = '100%';
            iframe.style.height = '600px';
            iframe.style.border = '1px solid red';
            document.body.prepend(iframe);
        }""", enforce_url)
        
        # Wait for all frames
        print("[*] Waiting for frames to load (25s)...", flush=True)
        gc_frame = None
        for i in range(50):
            for f in page.frames:
                if 'game-core' in f.url and 'index.html' in f.url:
                    gc_frame = f
                    print(f"[+] Game-core at {i*0.5:.0f}s!", flush=True)
                    break
            if gc_frame:
                break
            time.sleep(0.5)
        
        if gc_frame:
            print(f"  URL: {gc_frame.url[:200]}", flush=True)
            
            # Screenshot game-core
            gc_frame.screenshot(path="game_core_ready.png")
            
            # Get game-core details
            for attempt in range(20):
                gc_state = gc_frame.evaluate("""() => {
                    const canvases = document.querySelectorAll('canvas');
                    const images = document.querySelectorAll('img');
                    const buttons = document.querySelectorAll('button');
                    return {
                        canvases: canvases.length,
                        images: images.length,
                        buttons: buttons.length,
                        bodyLen: document.body?.innerHTML?.length || 0,
                        bodyPreview: document.body?.innerHTML?.substring(0, 500) || ''
                    };
                }""")
                
                if gc_state.get('canvases', 0) > 0 or gc_state.get('images', 0) > 4:
                    print(f"[+] Captcha game rendered at {attempt}s!", flush=True)
                    print(f"  State: {json.dumps(gc_state)[:500]}", flush=True)
                    gc_frame.screenshot(path=f"captcha_game_ready.png")
                    
                    # List all visual elements 
                    elements = gc_frame.evaluate("""() => {
                        const r = {};
                        r.canvases = Array.from(document.querySelectorAll('canvas')).map(c => ({
                            id: c.id,
                            width: c.width,
                            height: c.height,
                            className: c.className
                        }));
                        r.images = Array.from(document.querySelectorAll('img')).slice(0, 10).map(img => ({
                            src: img.src.substring(0, 100),
                            width: img.width,
                            height: img.height,
                            alt: img.alt
                        }));
                        r.buttons = Array.from(document.querySelectorAll('button')).slice(0, 10).map(b => ({
                            text: b.textContent?.substring(0, 30),
                            className: b.className
                        }));
                        return r;
                    }""")
                    print(f"\n  Elements: {json.dumps(elements, indent=2)[:1500]}", flush=True)
                    break
                time.sleep(1)
            else:
                print(f"[-] No captcha. State: {json.dumps(gc_state)[:300]}", flush=True)
        else:
            print("[-] No game-core frame found")
            print(f"  Frames: {[(f.url[:120], f.name[:30]) for f in page.frames]}", flush=True)
    
    page.screenshot(path="captcha_final_state.png")
    
    time.sleep(30)
    browser.close()
