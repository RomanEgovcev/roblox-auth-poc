"""Check enforcement frame state and try proper Arkose init with postMessage."""
import os, time, json, base64, sys

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

PUBLIC_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"
ENF_HASH = "504897d1cd342e063d4f67d90600cf04"

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
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    
    # Capture console errors
    errors = []
    def on_console(msg):
        try:
            if msg.type == 'error':
                errors.append(f"[{msg.type}] {msg.text[:200]}")
        except:
            pass
    page.on("console", on_console)
    
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        resp = response_info.value
        print(f"[+] Auth: {resp.status}", flush=True)
    except Exception as e:
        print(f"[-] Auth: {e}", flush=True)
    
    # ===== CREATE ENFORCEMENT IFRAME =====
    enforce_url = f"https://arkoselabs.roblox.com/v2/4.4.2/enforcement.{ENF_HASH}.html#{PUBLIC_KEY}&"
    
    page.evaluate("""(url) => {
        const div = document.createElement('div');
        div.id = 'arkose-0';
        div.style.width = '600px'; div.style.height = '500px';
        div.style.border = '2px solid red';
        document.body.prepend(div);
        
        const iframe = document.createElement('iframe');
        iframe.src = url;
        iframe.style.width = '100%'; iframe.style.height = '100%';
        iframe.style.border = 'none';
        div.appendChild(iframe);
    }""", enforce_url)
    
    # Check iframe was created
    time.sleep(2)
    iframe_check = page.evaluate("""() => ({
        arkose0: document.getElementById('arkose-0') ? 'exists' : 'missing',
        arkose0HTML: document.getElementById('arkose-0')?.innerHTML?.substring(0, 200) || '',
        iframeSrc: document.querySelector('#arkose-0 iframe')?.src?.substring(0, 250) || '',
    })""")
    print(f"[*] Iframe check: {json.dumps(iframe_check)}", flush=True)
    
    print("[*] Waiting for enforcement frame to load...", flush=True)
    
    # Wait for enforcement frame
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
    
    if not enf_frame:
        print("[-] No enforcement frame after 60s!", flush=True)
        print(f"Frames: {[(f.url[:120]) for f in page.frames]}", flush=True)
        
        # Check if enforcement is in DOM
        sec_check = page.evaluate("""() => {
            const a0 = document.getElementById('arkose-0');
            const iframe = a0?.querySelector('iframe');
            return {
                arkose0Exists: !!a0,
                iframeExists: !!iframe,
                iframeSrc: iframe?.src?.substring(0, 300) || '',
                iframeReadyState: iframe?.contentDocument?.readyState || 'N/A',
            };
        }""")
        print(f"DOM check: {json.dumps(sec_check)[:500]}", flush=True)
        
        page.screenshot(path="no_enf_60s.png")
        browser.close()
        sys.exit(1)
    
    # Monitor enforcement frame state
    print("\n[*] Checking enforcement frame state...", flush=True)
    for i in range(60):  # 30 seconds
        try:
            state = enf_frame.evaluate("""() => {
                const app = document.getElementById('app');
                return {
                    appExists: !!app,
                    appHTML: app ? app.innerHTML.substring(0, 300) : 'N/A',
                    bodyLen: document.body?.innerHTML?.length || 0,
                    scripts: document.querySelectorAll('script').length,
                    styleSheets: document.styleSheets?.length || 0,
                    url: window.location.href?.substring(0, 250) || '',
                    iframes: document.querySelectorAll('iframe').length,
                    challengeExists: !!document.getElementById('challenge'),
                };
            }""")
            
            if state.get('challengeExists'):
                print(f"[+] Challenge found at {i*0.5:.0f}s!", flush=True)
                enf_frame.screenshot(path="enf_challenge.png")
                break
            
            if i == 0:
                print(f"  Initial: appExists={state['appExists']}, bodyLen={state['bodyLen']}, scripts={state['scripts']}", flush=True)
            
        except Exception as e:
            if i % 10 == 0:
                print(f"  [{i*0.5:.0f}s] Error: {e}", flush=True)
        
        if i % 20 == 0 and i > 0:
            print(f"  [{i*0.5:.0f}s] Still waiting...", flush=True)
        time.sleep(0.5)
    
    # Print final state
    try:
        final = enf_frame.evaluate("""() => ({
            bodyLen: document.body?.innerHTML?.length || 0,
            appHTML: document.getElementById('app')?.innerHTML?.substring(0, 500) || 'N/A',
            iframes: document.querySelectorAll('iframe').length,
        })""")
        print(f"\n=== Final enforcement state ===", flush=True)
        print(json.dumps(final, indent=2)[:800], flush=True)
        enf_frame.screenshot(path="enf_final.png")
    except Exception as e:
        print(f"  Error reading final state: {e}", flush=True)
    
    # Try loading enforcement page in new browser context (standalone)
    print("\n[*] Trying enforcement page in new tab...", flush=True)
    enf_page = browser.new_page()
    enf_page.goto(enforce_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(10)
    
    for i in range(30):
        state = enf_page.evaluate("""() => ({
            bodyLen: document.body?.innerHTML?.length || 0,
            appHTML: document.getElementById('app')?.innerHTML?.substring(0, 300) || 'N/A',
            iframes: document.querySelectorAll('iframe').length,
            challenge: !!document.getElementById('challenge'),
        })""")
        if state.get('challenge'):
            print(f"[+] Challenge in standalone page at {i*0.5:.0f}s!", flush=True)
            enf_page.screenshot(path="enf_standalone.png")
            break
        if i == 0:
            print(f"  Initial: {json.dumps(state)[:300]}", flush=True)
        time.sleep(0.5)
    
    print(f"\n  Final standalone: {json.dumps(state, indent=2)[:400]}", flush=True)
    enf_page.screenshot(path="enf_standalone_final.png")
    
    time.sleep(5)
    browser.close()
