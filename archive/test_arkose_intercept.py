"""Intercept Arkose API to see why enforcement is not created."""
import os, time, json, base64, sys

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
    page.set_viewport_size({"width": 1280, "height": 900})
    
    arkose_api_calls = []
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
            return
        
        # Intercept Arkose API calls
        if 'arkoselabs.roblox.com' in url:
            resource_type = route.request.resource_type
            
            # Log API calls (but don't block)
            if 'api.js' in url or 'settings' in url or 'gt2/public_key' in url or 'enforcement.' in url and url.endswith('.js'):
                arkose_api_calls.append(f"REQ: {resource_type} {url[:200]}")
                route.continue_()
                return
            
            if '/fc/' in url or 'gfct' in url:
                arkose_api_calls.append(f"REQ: {resource_type} {url[:200]}")
                route.continue_()
                return
            
            # For enforcement HTML, intercept to see the hash
            if 'enforcement.' in url and url.endswith('.html'):
                arkose_api_calls.append(f"ENF_HTML: {url[:250]}")
                route.continue_()
                return
        
        route.continue_()
    
    page.route("**/*", intercept)
    
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
        browser.close()
        sys.exit(1)
    
    if not chal_meta_b64:
        print("[-] No challenge metadata!", flush=True)
        browser.close()
        sys.exit(1)
    
    original_meta = json.loads(base64.b64decode(chal_meta_b64).decode())
    print(f"[+] Meta: {json.dumps(original_meta, indent=2)[:500]}", flush=True)
    
    # ===== MANUAL TRIGGER =====
    modified_meta = original_meta.copy()
    if 'sharedParameters' in modified_meta:
        modified_meta['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
    new_meta_b64 = base64.b64encode(json.dumps(modified_meta).encode()).decode()
    chal_id = original_meta.get('challengeId', 'generic-challenge')
    chal_type = original_meta.get('challengeType', 'proofofwork')
    
    print(f"\n[*] Triggering enforcement...", flush=True)
    
    page.evaluate("""(args) => {
        const script = document.createElement('script');
        script.setAttribute('data-rblx-challenge', args.chalId);
        script.setAttribute('data-rblx-challenge-type', args.chalType);
        script.setAttribute('data-rblx-challenge-metadata', args.metaB64);
        document.head.appendChild(script);
        if (typeof window.PX?.setChallenge === 'function') {
            try { window.PX.setChallenge(JSON.parse(atob(args.metaB64))); }
            catch(e) { console.error('PX.setChallenge error:', e); }
        }
    }""", {'metaB64': new_meta_b64, 'chalId': chal_id, 'chalType': chal_type})
    
    # ===== WAIT and monitor =====
    print("[*] Monitoring Arkose API calls (30s)...", flush=True)
    for i in range(60):
        if i % 10 == 0 and i > 0:
            print(f"  [{i*0.5}s] API calls so far: {len(arkose_api_calls)}", flush=True)
            # Check DOM
            dom = page.evaluate("""() => ({
                arkose0: document.getElementById('arkose-0') ? document.getElementById('arkose-0').innerHTML.substring(0, 150) : 'missing',
                scripts: Array.from(document.querySelectorAll('script[id^=arkose-script]')).map(s => s.src.substring(0, 120)),
                iframes: document.querySelectorAll('#arkose-0 iframe').length,
            })""")
            print(f"    DOM: {json.dumps(dom)[:500]}", flush=True)
        time.sleep(0.5)
    
    # Print all Arkose API calls
    print(f"\n=== Arkose API calls ({len(arkose_api_calls)}) ===", flush=True)
    for c in arkose_api_calls:
        print(f"  {c}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    page.screenshot(path="arkose_monitor.png")
    time.sleep(5)
    browser.close()
