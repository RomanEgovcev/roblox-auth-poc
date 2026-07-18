"""Intercept auth response at CDP level (not JS fetch)."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")
patched = patched.replace("new EvalError", "new Error")

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
        elif 'auth.roblox.com' in url and '/v2/login' in url:
            # Forward request and modify response at CDP level
            resp = route.fetch()
            if resp.status == 403:
                chal_meta = resp.headers.get('rblx-challenge-metadata') or resp.headers.get('Rblx-Challenge-Metadata')
                print(f"[CDP] Auth 403, challenge metadata: {chal_meta[:80] if chal_meta else 'NONE'}", flush=True)
                if chal_meta:
                    try:
                        meta = json.loads(base64.b64decode(chal_meta).decode())
                        print(f"[CDP] Meta before: sharedParameters={json.dumps(meta.get('sharedParameters',{}))[:150]}", flush=True)
                        if meta.get('sharedParameters'):
                            meta['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
                            meta['sharedParameters']['renderNativeChallenge'] = True
                        new_meta_b64 = base64.b64encode(json.dumps(meta).encode()).decode()
                        
                        # Create new headers dict with modified challenge metadata
                        new_headers = dict(resp.headers)
                        # Headers might be case-sensitive; try both
                        if 'rblx-challenge-metadata' in new_headers:
                            new_headers['rblx-challenge-metadata'] = new_meta_b64
                        else:
                            # Find the matching header (case-insensitive)
                            for k in list(new_headers.keys()):
                                if k.lower() == 'rblx-challenge-metadata':
                                    new_headers[k] = new_meta_b64
                        
                        print(f"[CDP] Modified metadata: eligibleMethods={meta['sharedParameters']['eligibleMethods']}", flush=True)
                        
                        route.fulfill(
                            status=resp.status,
                            headers=new_headers,
                            body=resp.body()
                        )
                        print(f"[CDP] Response modified!", flush=True)
                        return
                    except Exception as e:
                        print(f"[CDP] Error modifying response: {e}", flush=True)
                
                # Fall through to default
                route.fulfill(resp)
            else:
                route.fulfill(resp)
        else:
            route.continue_()
    
    page.route("**/*", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
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
        
        # Check challenge metadata in the response
        chal = resp.headers.get('rblx-challenge-metadata') or resp.headers.get('Rblx-Challenge-Metadata')
        if chal:
            meta = json.loads(base64.b64decode(chal).decode())
            print(f"[+] Challenge metadata: sharedParameters={json.dumps(meta.get('sharedParameters',{}))[:200]}", flush=True)
        
    except Exception as e:
        print(f"[-] Auth: {e}", flush=True)
    
    time.sleep(5)
    
    # Check if enforcement was created
    enforce_state = page.evaluate("""() => {
        const r = {};
        r.arkose = document.getElementById('arkose-0') ? {
            html: document.getElementById('arkose-0').innerHTML.substring(0, 200),
            iframes: document.querySelectorAll('#arkose-0 iframe').length,
            children: document.getElementById('arkose-0').childElementCount
        } : 'missing';
        r.arkoseScript = document.getElementById('arkose-script-0') ? 'exists' : 'missing';
        r.genericChallenge = document.getElementById('generic-challenge-container-proofofwork') ? 'exists' : 'missing';
        r.challengeMeta = document.querySelector('script[data-rblx-challenge]') ? {
            type: document.querySelector('script[data-rblx-challenge]').getAttribute('data-rblx-challenge-type'),
            meta: document.querySelector('script[data-rblx-challenge]').getAttribute('data-rblx-challenge-metadata')?.substring(0, 150)
        } : 'missing';
        return r;
    }""")
    print(f"\n=== Enforcement state ===", flush=True)
    print(json.dumps(enforce_state, indent=2), flush=True)
    
    page.screenshot(path="cdp_route.png")
    
    time.sleep(5)
    browser.close()
