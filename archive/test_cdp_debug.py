"""CDP route + debug Challenge.js loading."""
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
    
    logs = []
    page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text[:300]}"))
    
    # Track all scripts that get loaded
    scripts = []
    page.on("response", lambda resp: scripts.append({
        'url': resp.url[:200],
        'status': resp.status,
        'type': resp.request.resource_type
    }) if resp.request.resource_type == 'script' else None)
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            print(f"[ROUTE] Patching: {url[:100]}", flush=True)
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        elif 'auth.roblox.com' in url and '/v2/login' in url:
            resp = route.fetch()
            if resp.status == 403:
                chal_meta = resp.headers.get('rblx-challenge-metadata') or resp.headers.get('Rblx-Challenge-Metadata')
                if chal_meta:
                    try:
                        meta = json.loads(base64.b64decode(chal_meta).decode())
                        if meta.get('sharedParameters'):
                            oldEM = meta['sharedParameters'].get('eligibleMethods', [])
                            meta['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
                            meta['sharedParameters']['renderNativeChallenge'] = True
                            new_meta_b64 = base64.b64encode(json.dumps(meta).encode()).decode()
                            
                            new_headers = dict(resp.headers)
                            for k in list(new_headers.keys()):
                                if k.lower() == 'rblx-challenge-metadata':
                                    new_headers[k] = new_meta_b64
                            
                            print(f"[CDP] Modified: eligibleMethods {oldEM} -> {meta['sharedParameters']['eligibleMethods']}", flush=True)
                            route.fulfill(status=resp.status, headers=new_headers, body=resp.body())
                            return
                    except Exception as e:
                        print(f"[CDP] Error: {e}", flush=True)
                route.fulfill(resp)
            else:
                route.fulfill(resp)
        else:
            route.continue_()
    
    page.route("**/*", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    
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
        
        chal = resp.headers.get('rblx-challenge-metadata') or resp.headers.get('Rblx-Challenge-Metadata')
        if chal:
            meta = json.loads(base64.b64decode(chal).decode())
            print(f"[+] Modified meta: eligibleMethods={meta.get('sharedParameters',{}).get('eligibleMethods')}", flush=True)
        
    except Exception as e:
        print(f"[-] Auth: {e}", flush=True)
    
    time.sleep(5)
    
    # Print challenge-related console logs
    print(f"\n=== Challenge/PX logs ===", flush=True)
    for log in logs:
        lower = log.lower()
        if any(k in lower for k in ['challenge', 'px', 'arkose', 'captcha', 'enforcement', 'proof', 'error']):
            print(f"  {log}", flush=True)
    
    # Print all scripts loaded
    print(f"\n=== Scripts with 'challenge' or 'px' in URL ===", flush=True)
    for s in scripts:
        url_lower = s['url'].lower()
        if any(k in url_lower for k in ['challenge', 'px', 'arkose', 'captcha', 'enforcement', 'proof']):
            print(f"  [{s['status']}] {s['url']}", flush=True)
    
    # Check DOM state
    state = page.evaluate("""() => {
        const r = {};
        r.scripts = Array.from(document.querySelectorAll('script[src]')).map(s => {
            const src = s.src || '';
            if (src.includes('challenge') || src.includes('px-') || src.includes('arkose'))
                return src.substring(0, 150);
            return null;
        }).filter(Boolean);
        
        r.challengeMeta = document.querySelector('script[data-rblx-challenge]') ? {
            id: document.querySelector('script[data-rblx-challenge]').getAttribute('data-rblx-challenge'),
            type: document.querySelector('script[data-rblx-challenge]').getAttribute('data-rblx-challenge-type'),
        } : 'missing';
        
        r.arkose0 = document.getElementById('arkose-0') ? 'exists' : 'missing';
        r.arkoseScript = document.getElementById('arkose-script-0') ? 'exists' : 'missing';
        r.genericChallenge = document.getElementById('generic-challenge-container-proofofwork') ? 'exists' : 'missing';
        
        // Also check the login page script (maybe it has the challenge handler)
        r.loginScripts = Array.from(document.querySelectorAll('script')).map(s => ({
            src: (s.src || '').substring(0, 200),
            textLen: (s.text || '').length,
            id: s.id
        })).filter(s => s.textLen > 50000 || s.src.includes('roblox.com'));
        
        return r;
    }""")
    print(f"\n=== DOM state ===", flush=True)
    print(json.dumps(state, indent=2)[:2000], flush=True)
    
    page.screenshot(path="cdp_debug.png")
    
    time.sleep(5)
    browser.close()
