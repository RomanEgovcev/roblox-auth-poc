"""Wait after auth and check if challenge elements appear, then manually trigger if needed."""
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
    
    auth_response = None
    chal_meta_b64 = None
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        auth_response = response_info.value
        print(f"[+] Auth: {auth_response.status}", flush=True)
        
        # Get challenge metadata from response
        for k, v in auth_response.headers.items():
            if k.lower() == 'rblx-challenge-metadata':
                chal_meta_b64 = v
                break
        
    except Exception as e:
        print(f"[-] Auth: {e}", flush=True)
    
    # Wait for challenge elements to appear
    print("[*] Waiting for challenge elements (5s)...", flush=True)
    arkose_appeared = False
    for i in range(10):
        dom = page.evaluate("""() => ({
            arkose0: document.getElementById('arkose-0') ? 'exists' : 'missing',
            arkoseScript: document.getElementById('arkose-script-0') ? 'exists' : 'missing',
            challengeScript: document.querySelector('script[data-rblx-challenge]') ? 'exists' : 'missing',
            genericChallenge: document.getElementById('generic-challenge-container-proofofwork') ? 'exists' : 'missing'
        })""")
        
        if dom.get('arkose0') == 'exists' or dom.get('challengeScript') == 'exists':
            print(f"[+] Challenge elements found at {i}s!", flush=True)
            print(f"  DOM: {json.dumps(dom)}", flush=True)
            arkose_appeared = True
            break
        
        time.sleep(0.5)
    else:
        print(f"[-] No challenge elements after 5s", flush=True)
        print(f"  DOM: {json.dumps(dom)}", flush=True)
    
    if not arkose_appeared and chal_meta_b64:
        # Manually create challenge elements
        print(f"\n[*] Manually creating challenge elements...", flush=True)
        chal_meta = json.loads(base64.b64decode(chal_meta_b64).decode())
        
        modified_meta = chal_meta.copy()
        if 'sharedParameters' in modified_meta:
            modified_meta['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
            modified_meta['sharedParameters']['renderNativeChallenge'] = True
        
        new_meta_b64 = base64.b64encode(json.dumps(modified_meta).encode()).decode()
        chal_id = chal_meta.get('challengeId', 'generic-challenge')
        chal_type = chal_meta.get('challengeType', 'proofofwork')
        
        # Bundle arguments into a single dict
        result = page.evaluate("""(args) => {
            const r = {};
            r.PX_type = typeof window._px;
            r.PX_setChallenge = typeof window.PX?.setChallenge;
            
            // Create the script element with modified metadata
            const script = document.createElement('script');
            script.setAttribute('data-rblx-challenge', args.chalId);
            script.setAttribute('data-rblx-challenge-type', args.chalType);
            script.setAttribute('data-rblx-challenge-metadata', args.metaB64);
            document.head.appendChild(script);
            r.scriptAdded = true;
            
            // Also try PX.setChallenge if it exists
            if (typeof window.PX?.setChallenge === 'function') {
                try {
                    const chalData = JSON.parse(atob(args.metaB64));
                    window.PX.setChallenge(chalData);
                    r.setChallengeCalled = true;
                } catch(e) { r.setChallengeError = e.message; }
            }
            
            return r;
        }""", {
            'metaB64': new_meta_b64,
            'chalId': chal_id,
            'chalType': chal_type
        })
        print(f"  Manual trigger: {json.dumps(result)}", flush=True)
        
        time.sleep(2)
        
        post = page.evaluate("""() => ({
            arkose0: document.getElementById('arkose-0') ? {
                html: document.getElementById('arkose-0').innerHTML.substring(0, 100),
                iframes: document.querySelectorAll('#arkose-0 iframe').length
            } : 'missing',
            arkoseScript: document.getElementById('arkose-script-0') ? 'exists' : 'missing',
            challengeScript: document.querySelector('script[data-rblx-challenge]') ? 'exists' : 'missing',
            genericChallenge: document.getElementById('generic-challenge-container-proofofwork') ? 'exists' : 'missing'
        })""")
        print(f"\n=== Post-trigger DOM ===", flush=True)
        print(json.dumps(post, indent=2), flush=True)
        
        if post.get('arkose0') != 'missing':
            # Wait for iframe to appear
            print("[*] Waiting for iframe in arkose-0...", flush=True)
            for i in range(10):
                check = page.evaluate("""() => ({
                    iframes: document.querySelectorAll('#arkose-0 iframe').length,
                    src: document.querySelector('#arkose-0 iframe')?.src?.substring(0, 200) || ''
                })""")
                if check.get('iframes', 0) > 0:
                    print(f"[+] Iframe found at {i}s!", flush=True)
                    print(f"  SRC: {check['src']}", flush=True)
                    break
                time.sleep(0.5)
            else:
                print(f"[-] No iframe after 5s", flush=True)
    
    page.screenshot(path="manual_trigger_final.png")
    
    time.sleep(5)
    browser.close()
