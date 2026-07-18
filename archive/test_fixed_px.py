"""Only patch new Function, NOT new EvalError. Use CDP route for auth."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

# CRITICAL: Only patch new Function("return this")() - this is blocked by CSP
# Do NOT patch new EvalError - this works fine under CSP and would break PX
patched = px_script.replace('new Function("return this")()', "(window||self||globalThis)")

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
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        elif 'auth.roblox.com' in url and '/v2/login' in url:
            resp = route.fetch()
            if resp.status == 403:
                chal_meta = None
                for k, v in resp.headers.items():
                    if k.lower() == 'rblx-challenge-metadata':
                        chal_meta = v
                        break
                if chal_meta:
                    try:
                        meta = json.loads(base64.b64decode(chal_meta).decode())
                        if meta.get('sharedParameters'):
                            old_em = meta['sharedParameters'].get('eligibleMethods', [])
                            meta['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
                            meta['sharedParameters']['renderNativeChallenge'] = True
                            new_meta_b64 = base64.b64encode(json.dumps(meta).encode()).decode()
                            
                            new_headers = dict(resp.headers)
                            for k in list(new_headers.keys()):
                                if k.lower() == 'rblx-challenge-metadata':
                                    new_headers[k] = new_meta_b64
                            
                            print(f"[CDP] eligibleMethods: {old_em} -> {meta['sharedParameters']['eligibleMethods']}", flush=True)
                            route.fulfill(status=resp.status, headers=new_headers, body=resp.body())
                            return
                    except Exception as e:
                        print(f"[CDP] Error: {e}", flush=True)
            route.fulfill(status=resp.status, headers=dict(resp.headers), body=resp.body())
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
    
    # Check state
    state = page.evaluate("""() => {
        const r = {};
        r.arkose0 = document.getElementById('arkose-0') ? {
            html: document.getElementById('arkose-0').innerHTML.substring(0, 100),
            iframes: document.querySelectorAll('#arkose-0 iframe').length
        } : 'missing';
        r.arkoseScript = document.getElementById('arkose-script-0') ? 'exists' : 'missing';
        r.genericChallenge = document.getElementById('generic-challenge-container-proofofwork') ? 'exists' : 'missing';
        r.challengeScript = document.querySelector('script[data-rblx-challenge]') ? 
            document.querySelector('script[data-rblx-challenge]').outerHTML.substring(0, 200) : 'missing';
        r.PX = typeof window._px;
        r.PX_setChallenge = typeof window.PX?.setChallenge;
        r.ph = window.ph;
        r.oC = typeof window.oC;
        return r;
    }""")
    print(f"\n=== State ===", flush=True)
    print(json.dumps(state, indent=2), flush=True)
    
    print(f"\n=== Error/PX logs ===", flush=True)
    for log in logs:
        lower = log.lower()
        if any(k in lower for k in ['error', 'px', 'challenge', 'arkose', 'eligible']):
            print(f"  {log}", flush=True)
    
    page.screenshot(path="no_evalerror_patch.png")
    
    time.sleep(5)
    browser.close()
