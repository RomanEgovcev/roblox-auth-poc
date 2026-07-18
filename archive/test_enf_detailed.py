"""Check enforcement frame console and scripts."""
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
    
    enf_logs = []
    def on_console(msg):
        try:
            loc = getattr(msg, 'location', None) or {}
            url = loc.get('url', '') if isinstance(loc, dict) else (loc.url if hasattr(loc, 'url') else '')
            if 'arkoselabs' in url or 'enforcement' in url:
                enf_logs.append(f"[{msg.type}] {msg.text[:200]}")
        except:
            pass
    page.on("console", on_console)
    
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
        
        page.evaluate("""(url) => {
            const iframe = document.createElement('iframe');
            iframe.src = url;
            iframe.style.width = '100%';
            iframe.style.height = '600px';
            document.body.prepend(iframe);
        }""", enforce_url)
        
        # Wait for enforcement frame
        print("[*] Waiting for enforcement frame (60s)...", flush=True)
        enf_frame = None
        for i in range(120):
            for f in page.frames:
                if 'arkoselabs' in f.url and 'enforcement.' in f.url:
                    enf_frame = f
                    break
            if enf_frame:
                print(f"[+] Enforcement frame at {i*0.5:.0f}s!", flush=True)
                break
            time.sleep(0.5)
        
        if enf_frame:
            print(f"  URL: {enf_frame.url[:200]}", flush=True)
            
            # Wait and check enforcement frame content periodically
            for check in range(6):
                time.sleep(5)
                
                try:
                    enf_state = enf_frame.evaluate("""() => {
                        const scripts = Array.from(document.scripts).map(s => ({
                            src: (s.src || '').substring(0, 100),
                            id: s.id,
                            loaded: !!s.src
                        }));
                        const iframes = Array.from(document.querySelectorAll('iframe')).map(f => f.src).filter(Boolean);
                        return {
                            bodyLen: document.body?.innerHTML?.length || 0,
                            scripts: scripts.slice(0, 15),
                            iframes: iframes.slice(0, 5),
                            hasChallenge: !!document.getElementById('challenge'),
                            hasFunCaptcha: !!document.getElementById('FunCaptcha'),
                            appHTML: document.getElementById('app')?.innerHTML?.substring(0, 500) || ''
                        };
                    }""")
                    print(f"\n  [{check*5+5}s] Enforcement state:", flush=True)
                    print(f"    bodyLen={enf_state['bodyLen']}, scripts={len(enf_state['scripts'])}, iframes={len(enf_state['iframes'])}", flush=True)
                    if enf_state.get('hasChallenge'):
                        print(f"    *** CAPTCHA ACTIVE! ***", flush=True)
                    if enf_state.get('hasFunCaptcha'):
                        print(f"    *** FUNCAPTCHA ACTIVE! ***", flush=True)
                    if enf_state.get('iframes'):
                        print(f"    Iframes: {json.dumps(enf_state['iframes'][:3])}", flush=True)
                    if len(enf_state['scripts']) > 1:
                        print(f"    Scripts loaded: {len(enf_state['scripts'])}", flush=True)
                        for s in enf_state['scripts'][:5]:
                            if s['src']:
                                print(f"      - {s['id'] or ''}: {s['src']}", flush=True)
                except Exception as e:
                    print(f"  [{check*5+5}s] Error: {e}", flush=True)
            
            # Print enforcement logs
            print(f"\n=== Enforcement logs ({len(enf_logs)}) ===", flush=True)
            for log in enf_logs[-10:]:
                print(f"  {log}", flush=True)
            
            # Take screenshot of enforcement page
            try:
                enf_frame.screenshot(path="enf_final.png")
            except:
                pass
    
    page.screenshot(path="final.png")
    time.sleep(5)
    browser.close()
