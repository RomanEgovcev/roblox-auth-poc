"""Robust: wait up to 60s for all frames to load."""
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
            document.body.prepend(iframe);
        }""", enforce_url)
        
        # Wait for game-core with 60s timeout
        print("[*] Waiting for game-core frame (60s)...", flush=True)
        gc_frame = None
        for i in range(120):
            for f in page.frames:
                if 'game-core' in f.url and 'index.html' in f.url:
                    gc_frame = f
                    break
            if gc_frame:
                print(f"[+] Game-core at {i*0.5:.0f}s!", flush=True)
                break
            if i % 20 == 0 and i > 0:
                print(f"  [{i*0.5:.0f}s] Checking... Frames: {len(page.frames)}", flush=True)
            time.sleep(0.5)
        
        if gc_frame:
            gc_frame.screenshot(path="gc_final.png")
            
            for i in range(20):
                gc_state = gc_frame.evaluate("""() => ({
                    canvases: document.querySelectorAll('canvas').length,
                    images: document.querySelectorAll('img').length
                })""")
                if gc_state.get('canvases', 0) > 0 or gc_state.get('images', 0) > 4:
                    print(f"[+] Captcha rendered at {i}s!\n  {json.dumps(gc_state)}", flush=True)
                    gc_frame.screenshot(path="captcha_final.png")
                    
                    # Get full element info
                    elements = gc_frame.evaluate("""() => ({
                        canvases: Array.from(document.querySelectorAll('canvas')).slice(0,5).map(c => ({
                            id: c.id, width: c.width, height: c.height
                        })),
                        images: Array.from(document.querySelectorAll('img')).slice(0,10).map(i => ({
                            src: i.src.substring(0,100),
                            width: i.width, height: i.height
                        })),
                        buttons: Array.from(document.querySelectorAll('button')).slice(0,10).map(b => ({
                            text: b.textContent?.substring(0,20),
                            className: b.className?.substring(0,50)
                        }))
                    })""")
                    print(f"  Elements: {json.dumps(elements)[:2000]}", flush=True)
                    break
                time.sleep(1)
            else:
                print(f"[-] No captcha after 20s", flush=True)
        else:
            print(f"[-] No game-core. Final frames:", flush=True)
            for fi, f in enumerate(page.frames):
                try:
                    content = f.evaluate("() => document.body?.innerHTML?.substring(0,100) || 'empty'")
                    has_app = f.evaluate("() => !!document.getElementById('app')")
                    print(f"  [{fi}] {f.url[:100]} hasApp={has_app} body='{content[:80]}'", flush=True)
                except:
                    print(f"  [{fi}] {f.url[:100]} [cross-origin]", flush=True)
    
    page.screenshot(path="final.png")
    time.sleep(15)
    browser.close()
