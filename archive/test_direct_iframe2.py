"""Create iframe and wait for navigation to complete."""
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
        
        enforce_url = f"https://arkoselabs.roblox.com/v2/4.4.2/enforcement.504897d1cd342e063d4f67d90600cf04.html#476068BF-9607-4799-B53D-966BE98E2B81&{session_id}"
        
        print(f"[*] Creating iframe for: {enforce_url[:200]}", flush=True)
        
        page.evaluate("""(url) => {
            const iframe = document.createElement('iframe');
            iframe.src = url;
            iframe.style.width = '100%';
            iframe.style.height = '400px';
            iframe.style.border = '1px solid red';
            document.body.prepend(iframe);
        }""", enforce_url)
        
        # Wait for frames to update
        print("[*] Waiting for enforcement frame navigation (30s)...", flush=True)
        enf_frame = None
        for i in range(60):
            for f in page.frames:
                if 'arkoselabs' in f.url and 'enforcement.' in f.url:
                    enf_frame = f
                    print(f"[+] Enforcement frame at {i*0.5:.0f}s!", flush=True)
                    print(f"  URL: {f.url[:200]}", flush=True)
                    break
            if enf_frame:
                break
            time.sleep(0.5)
        
        if enf_frame:
            # Take screenshot and check content
            enf_frame.screenshot(path="enf_direct.png")
            
            enf_content = enf_frame.evaluate("""() => ({
                bodyLen: document.body?.innerHTML?.length || 0,
                appHTML: document.getElementById('app')?.innerHTML?.substring(0, 300) || 'empty',
                scripts: Array.from(document.querySelectorAll('script')).map(s => ({
                    src: (s.src || '').substring(0, 150), id: s.id
                })).filter(s => s.id || s.src).slice(0, 10),
                iframes: Array.from(document.querySelectorAll('iframe')).map(f => f.src).filter(Boolean).slice(0, 5)
            })""")
            print(f"\n=== Enforcement content ===", flush=True)
            print(json.dumps(enf_content, indent=2)[:1500], flush=True)
            
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
                gc_frame.screenshot(path="gc_direct.png")
                for i in range(20):
                    gc_state = gc_frame.evaluate("""() => ({
                        canvases: document.querySelectorAll('canvas').length,
                        images: document.querySelectorAll('img').length
                    })""")
                    if gc_state.get('canvases', 0) > 0 or gc_state.get('images', 0) > 3:
                        print(f"[+] Captcha at {i}s!\n  {json.dumps(gc_state)}", flush=True)
                        gc_frame.screenshot(path="captcha_direct.png")
                        break
                    time.sleep(1)
                else:
                    print(f"[-] No captcha. State: {json.dumps(gc_state)}", flush=True)
            else:
                print(f"[-] No game-core. Child frames: {[(f.url[:100], f.name) for f in enf_frame.child_frames]}", flush=True)
        else:
            print(f"[-] No enforcement frame after 30s", flush=True)
            print(f"  Frames: {[(f.url[:120], f.name) for f in page.frames]}", flush=True)
            
            # Check if iframe DOM element exists with correct src
            iframe_src = page.evaluate("""() => {
                const iframe = document.querySelector('iframe[src*=\"arkoselabs\"]');
                return iframe ? iframe.src.substring(0, 200) : 'missing';
            }""")
            print(f"  Iframe element src: {iframe_src}", flush=True)
        
        print(f"\n=== Arkose responses ({len(arkose_responses)}) ===", flush=True)
        for url, status, rtype in arkose_responses:
            print(f"  [{status}] {rtype:12s} {url}", flush=True)
    
    page.screenshot(path="direct_final.png")
    time.sleep(10)
    browser.close()
