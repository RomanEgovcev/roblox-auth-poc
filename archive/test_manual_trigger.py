"""Immediately after auth 403, check DOM and manually trigger challenge."""
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
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        auth_response = response_info.value
        print(f"[+] Auth: {auth_response.status}", flush=True)
        
        # IMMEDIATELY check DOM after auth
        dom_check = page.evaluate("""() => {
            return {
                arkose0: document.getElementById('arkose-0') ? 'exists' : 'missing',
                arkoseIframes: document.querySelectorAll('#arkose-0 iframe').length,
                arkoseScript: document.getElementById('arkose-script-0') ? {
                    src: document.getElementById('arkose-script-0').src?.substring(0, 150),
                    textLen: document.getElementById('arkose-script-0').text?.length || 0
                } : 'missing',
                arkoseScriptAny: Array.from(document.querySelectorAll('script')).filter(s => s.id?.startsWith('arkose-script')).map(s => ({
                    id: s.id,
                    src: (s.src || '').substring(0, 150)
                })),
                challengeScript: document.querySelector('script[data-rblx-challenge]') ? 'exists' : 'missing',
                allScripts: Array.from(document.querySelectorAll('script')).map(s => ({
                    id: s.id,
                    src: (s.src || '').substring(0, 200),
                    dataAttrs: Array.from(s.attributes).filter(a => a.name.startsWith('data-')).map(a => a.name + '=' + a.value.substring(0, 50))
                })).filter(s => s.id?.includes('arkose') || s.src?.includes('arkoselabs') || s.dataAttrs?.length > 0),
                genericChallenge: document.getElementById('generic-challenge-container-proofofwork') ? 'exists' : 'missing',
                PX: typeof window._px,
                PX2: typeof window.PX
            };
        }""")
        print(f"\n=== Immediate DOM check ===", flush=True)
        print(json.dumps(dom_check, indent=2)[:2000], flush=True)
        
        # Read challenge metadata from response
        chal_meta_b64 = None
        for k, v in auth_response.headers.items():
            if k.lower() == 'rblx-challenge-metadata':
                chal_meta_b64 = v
                break
        
        if chal_meta_b64:
            chal_meta = json.loads(base64.b64decode(chal_meta_b64).decode())
            print(f"\n=== Challenge metadata ===", flush=True)
            print(f"  sessionId: {chal_meta.get('sessionId')}", flush=True)
            print(f"  sharedParameters: {json.dumps(chal_meta.get('sharedParameters', {}), indent=2)[:500]}", flush=True)
            
            # Check if eligibleMethods is already populated
            sp = chal_meta.get('sharedParameters', {})
            print(f"\n  eligibleMethods: {sp.get('eligibleMethods')}")
            print(f"  renderNative: {sp.get('renderNativeChallenge')}")
            
            # If enforcement not created, try to trigger it manually
            if dom_check.get('arkose0') == 'missing':
                print(f"\n[*] Manually creating challenge elements...", flush=True)
                
                # Modify eligibleMethods
                modified_meta = chal_meta.copy()
                if 'sharedParameters' in modified_meta:
                    modified_meta['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
                    modified_meta['sharedParameters']['renderNativeChallenge'] = True
                
                new_meta_b64 = base64.b64encode(json.dumps(modified_meta).encode()).decode()
                
                # Try to create the script element and trigger enforcement
                result = page.evaluate("""(chalMetaB64, chalType, chalId) => {
                    const r = {};
                    
                    // Check if PX.setChallenge exists
                    r.PX_setChallenge = typeof window.PX?.setChallenge;
                    r.PX_getEnforcement = typeof window.PX?.getEnforcement;
                    
                    // Try creating the data script element the way Challenge.js expects
                    const script = document.createElement('script');
                    script.setAttribute('data-rblx-challenge', chalId);
                    script.setAttribute('data-rblx-challenge-type', chalType);
                    script.setAttribute('data-rblx-challenge-metadata', chalMetaB64);
                    document.head.appendChild(script);
                    r.scriptAdded = true;
                    
                    // Check if any challenge process was triggered
                    setTimeout(() => {
                        r.afterScript = {
                            arkose0: document.getElementById('arkose-0') ? 'exists' : 'missing',
                            arkoseScript: document.getElementById('arkose-script-0') ? 'exists' : 'missing',
                            iframes: document.querySelectorAll('#arkose-0 iframe').length
                        };
                    }, 100);
                    
                    return r;
                }""", new_meta_b64, 
                    chal_meta.get('challengeType', 'proofofwork'), 
                    chal_meta.get('challengeId', 'generic-challenge'))
                
                print(f"  Manual trigger result: {json.dumps(result)}", flush=True)
                time.sleep(1)
                
                # Check after triggering
                post_trigger = page.evaluate("""() => ({
                    arkose0: document.getElementById('arkose-0') ? {
                        html: document.getElementById('arkose-0').innerHTML.substring(0, 100),
                        iframes: document.querySelectorAll('#arkose-0 iframe').length
                    } : 'missing',
                    arkoseScript: document.getElementById('arkose-script-0') ? 'exists' : 'missing',
                    challengeScript: document.querySelector('script[data-rblx-challenge]') ? 'exists' : 'missing'
                })""")
                print(f"\n=== Post-trigger DOM ===", flush=True)
                print(json.dumps(post_trigger, indent=2), flush=True)
    
    except Exception as e:
        print(f"[-] Auth: {e}", flush=True)
    
    time.sleep(5)
    page.screenshot(path="manual_trigger.png")
    
    time.sleep(5)
    browser.close()
