"""CDP route: modify both headers AND body of auth 403."""
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
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            print(f"[ROUTE] Patching PX", flush=True)
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        elif 'auth.roblox.com' in url and '/v2/login' in url:
            resp = route.fetch()
            if resp.status == 403:
                try:
                    body = resp.body()
                    body_json = json.loads(body)
                    print(f"[CDP] Auth 403 body keys: {list(body_json.keys())}", flush=True)
                    
                    # Check for challenge metadata in body
                    if 'challengeMetadata' in body_json:
                        old_cm = body_json['challengeMetadata']
                        cm = json.loads(base64.b64decode(old_cm).decode())
                        print(f"[CDP] Body challenge metadata: {json.dumps(cm)[:200]}", flush=True)
                        
                        if 'sharedParameters' in cm:
                            old_em = cm['sharedParameters'].get('eligibleMethods', [])
                            cm['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
                            cm['sharedParameters']['renderNativeChallenge'] = True
                            new_cm_b64 = base64.b64encode(json.dumps(cm).encode()).decode()
                            body_json['challengeMetadata'] = new_cm_b64
                            print(f"[CDP] Body modified: eligibleMethods {old_em} -> {cm['sharedParameters']['eligibleMethods']}", flush=True)
                        
                        new_body = json.dumps(body_json)
                        
                        # Also fix headers
                        new_headers = dict(resp.headers)
                        for k in list(new_headers.keys()):
                            if k.lower() == 'rblx-challenge-metadata':
                                new_headers[k] = new_cm_b64
                        
                        print(f"[CDP] Both headers and body modified!", flush=True)
                        route.fulfill(status=resp.status, headers=new_headers, body=new_body)
                        return
                    
                    # No body challenge metadata
                    print(f"[CDP] No challengeMetadata in body", flush=True)
                    route.fulfill(resp)
                except Exception as e:
                    print(f"[CDP] Error: {e}", flush=True)
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
        
    except Exception as e:
        print(f"[-] Auth: {e}", flush=True)
    
    time.sleep(8)
    
    # Check enforcement state
    state = page.evaluate("""() => {
        const r = {};
        r.arkose0 = document.getElementById('arkose-0') ? {
            html: document.getElementById('arkose-0').innerHTML.substring(0, 100),
            iframes: document.querySelectorAll('#arkose-0 iframe').length
        } : 'missing';
        r.arkoseScript = document.getElementById('arkose-script-0') ? 'exists' : 'missing';
        r.genericChallenge = document.getElementById('generic-challenge-container-proofofwork') ? {
            display: document.getElementById('generic-challenge-container-proofofwork').style.display
        } : 'missing';
        r.challengeScript = document.querySelector('script[data-rblx-challenge]') ? {
            id: document.querySelector('script[data-rblx-challenge]').getAttribute('data-rblx-challenge')
        } : 'missing';
        return r;
    }""")
    print(f"\n=== State ===", flush=True)
    print(json.dumps(state, indent=2), flush=True)
    
    # Check console for challenge-related errors
    print(f"\n=== Challenge-related logs ===", flush=True)
    for log in logs:
        lower = log.lower()
        if any(k in lower for k in ['challenge', 'arkose', 'captcha', 'enforcement', 'proof', 'eligible']):
            print(f"  {log}", flush=True)
    
    page.screenshot(path="cdp_body_mod.png")
    
    time.sleep(5)
    browser.close()
