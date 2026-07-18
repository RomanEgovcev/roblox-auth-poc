"""Access about:blank frames that contain enforcement."""
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
            iframe.style.height = '400px';
            document.body.prepend(iframe);
        }""", enforce_url)
        
        # Wait for about:blank frames
        print("[*] Waiting and checking about:blank frames (20s)...", flush=True)
        for i in range(40):
            frames = page.frames
            
            # Check all about:blank frames
            for fi, f in enumerate(frames):
                if f.url == 'about:blank' and f.name not in ['downloadInstallerIFrame', '']:
                    print(f"[+] Interesting about:blank frame at {i*0.5:.0f}s: [{fi}] name={f.name}", flush=True)
            
            time.sleep(0.5)
            
            # Every few seconds, try evaluating content in each frame
            if i % 10 == 0:
                for fi, f in enumerate(frames):
                    if f.url in ['about:blank', '']:
                        try:
                            content = f.evaluate("""() => {
                                return {
                                    bodyLen: document.body?.innerHTML?.length || 0,
                                    bodyPreview: document.body?.innerHTML?.substring(0, 200) || '',
                                    hasApp: !!document.getElementById('app')
                                };
                            }""")
                            if content.get('hasApp') or content.get('bodyLen', 0) > 0:
                                print(f"[!] Frame [{fi}] content found! URL: '{f.url}' name='{f.name}'", flush=True)
                                print(f"    Body: {json.dumps(content)[:300]}", flush=True)
                        except Exception as e:
                            pass  # Cross-origin error is expected for some frames
        
        # Final check of all frames
        print(f"\n[*] Final frame check:", flush=True)
        for fi, f in enumerate(page.frames):
            print(f"  [{fi}] url='{f.url[:100]}' name='{f.name}'", flush=True)
            
            # Try to evaluate in each frame
            try:
                content = f.evaluate("""() => ({
                    bodyLen: document.body?.innerHTML?.length || 0,
                    htmlStart: document.body?.innerHTML?.substring(0, 200) || 'empty',
                    hasApp: !!document.getElementById('app'),
                    scripts: Array.from(document.querySelectorAll('script')).map(s => s.id || (s.src ? s.src.substring(0,80) : 'inline')).filter(Boolean).slice(0,5)
                })""")
                print(f"    Content: {json.dumps(content)[:300]}", flush=True)
            except Exception as e:
                error_msg = str(e)[:100]
                if 'cross-origin' in error_msg.lower() or 'blocked' in error_msg.lower():
                    print(f"    [Cross-origin - expected]", flush=True)
                else:
                    print(f"    [Error: {error_msg}]", flush=True)
    
    page.screenshot(path="about_blank_frames.png")
    time.sleep(5)
    browser.close()
