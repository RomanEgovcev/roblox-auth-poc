"""After arkose0 appears, manually trigger enforcement with modified metadata."""
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
    
    arkose_urls = []
    
    def track_arkose(response):
        url = response.url
        if 'arkoselabs.roblox.com' in url or 'ecsv2.roblox.com' in url:
            arkose_urls.append({'url': url[:200], 'status': response.status, 'type': response.request.resource_type})
    
    page.on("response", track_arkose)
    
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
        
        auth_response = response_info.value
        
        for k, v in auth_response.headers.items():
            if k.lower() == 'rblx-challenge-metadata':
                chal_meta_b64 = v
                break
        
        print(f"[+] Auth: {auth_response.status}", flush=True)
        if chal_meta_b64:
            # Parse and store the original metadata
            original_meta = json.loads(base64.b64decode(chal_meta_b64).decode())
            print(f"[+] eligibleMethods: {original_meta.get('sharedParameters',{}).get('eligibleMethods')}", flush=True)
    except Exception as e:
        print(f"[-] Auth: {e}", flush=True)
    
    # Wait for arkose0 container
    print("[*] Waiting for arkose-0 container...", flush=True)
    container_appeared = False
    for i in range(15):
        dom = page.evaluate("""() => ({
            arkose0: document.getElementById('arkose-0') ? 'exists' : 'missing',
            arkoseIframes: document.querySelectorAll('#arkose-0 iframe').length
        })""")
        
        if dom.get('arkose0') == 'exists':
            if not container_appeared:
                container_appeared = True
                print(f"[+] arkose-0 container found at {i}s!", flush=True)
        
        time.sleep(0.5)
    
    if not container_appeared:
        print("[-] arkose-0 container never appeared", flush=True)
    else:
        # Now TRIGGER enforcement creation with MODIFIED metadata
        if chal_meta_b64:
            modified_meta = original_meta.copy()
            if 'sharedParameters' in modified_meta:
                modified_meta['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
                modified_meta['sharedParameters']['renderNativeChallenge'] = True
            
            new_meta_b64 = base64.b64encode(json.dumps(modified_meta).encode()).decode()
            chal_id = original_meta.get('challengeId', 'generic-challenge')
            chal_type = original_meta.get('challengeType', 'proofofwork')
            
            print(f"\n[*] Triggering enforcement with modified metadata...", flush=True)
            print(f"  Setting eligibleMethods to: ['captcha', 'proofofwork']", flush=True)
            
            # Clear any existing arkose URLs to track fresh ones
            arkose_urls.clear()
            
            result = page.evaluate("""(args) => {
                const r = {};
                r.PX_setChallenge = typeof window.PX?.setChallenge;
                r.PX_getEnforcement = typeof window.PX?.getEnforcement;
                r.oC_type = typeof window.oC;
                r.ph = window.ph;
                
                // Method 1: Create script[data-rblx-challenge] element
                const script = document.createElement('script');
                script.setAttribute('data-rblx-challenge', args.chalId);
                script.setAttribute('data-rblx-challenge-type', args.chalType);
                script.setAttribute('data-rblx-challenge-metadata', args.metaB64);
                document.head.appendChild(script);
                r.scriptAdded = true;
                
                // Method 2: Call PX.setChallenge if available
                if (typeof window.PX?.setChallenge === 'function') {
                    try {
                        const chalData = JSON.parse(atob(args.metaB64));
                        window.PX.setChallenge(chalData);
                        r.setChallengeCalled = true;
                    } catch(e) { r.setChallengeError = e.message; }
                }
                
                // Method 3: Directly trigger setupEnforcement if available
                r.challengePromise_type = typeof window.challengePromise;
                r.setupEnforcement_type = typeof window.setupEnforcement;
                
                return r;
            }""", {
                'metaB64': new_meta_b64,
                'chalId': chal_id,
                'chalType': chal_type
            })
            print(f"  Result: {json.dumps(result)}", flush=True)
        
        # Wait for enforcement to load
        print(f"\n[*] Waiting for enforcement iframe (10s)...", flush=True)
        iframe_found = False
        for i in range(20):
            dom = page.evaluate("""() => ({
                iframes: document.querySelectorAll('#arkose-0 iframe').length,
                src: document.querySelector('#arkose-0 iframe')?.src?.substring(0, 200) || '',
                arkoseScript: document.getElementById('arkose-script-0') ? 'exists' : 'missing',
                scripts: Array.from(document.querySelectorAll('script')).filter(s => s.id?.startsWith('arkose-script')).map(s => ({id: s.id, src: (s.src || '').substring(0, 150)}))
            })""")
            
            if dom.get('iframes', 0) > 0:
                print(f"[+] Enforcement iframe found at {i}s!", flush=True)
                print(f"  SRC: {dom['src']}", flush=True)
                iframe_found = True
                break
            
            if dom.get('arkoseScript') != 'missing':
                scripts_in_dom = dom.get('scripts', [])
                if scripts_in_dom:
                    print(f"[+] Arkose script found at {i}s!", flush=True)
                    print(f"  Scripts: {json.dumps(scripts_in_dom)}", flush=True)
            
            time.sleep(0.5)
        
        if not iframe_found:
            print(f"[-] No iframe after 10s", flush=True)
            print(f"  Final DOM: {json.dumps(dom, indent=2)}", flush=True)
            
            # Try waiting for arkose script to load 
            for i in range(10):
                dom = page.evaluate("""() => ({
                    arkoseScript: document.getElementById('arkose-script-0') ? 'exists' : 'missing',
                    scripts: Array.from(document.querySelectorAll('script')).filter(s => s.id?.startsWith('arkose-script')).map(s => ({id: s.id, src: (s.src || '').substring(0, 150)})),
                    arkose0: document.getElementById('arkose-0') ? document.getElementById('arkose-0').innerHTML.substring(0, 100) : 'missing'
                })""")
                if dom.get('arkoseScript') != 'missing' or dom.get('scripts'):
                    print(f"[+] Script appeared at {i+10}s!", flush=True)
                    print(f"  DOM: {json.dumps(dom)}", flush=True)
                    break
                time.sleep(1)
            else:
                print(f"[-] No scripts created. Trying different approach...", flush=True)
        
        # Print Arkose network requests
        print(f"\n=== Arkose network requests ({len(arkose_urls)}) ===", flush=True)
        for r in arkose_urls:
            print(f"  [{r['status']}] {r['type']} {r['url']}", flush=True)
    
    page.screenshot(path="manual_trigger_final.png")
    
    time.sleep(5)
    browser.close()
