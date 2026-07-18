"""Get FULL Arkose settings response."""
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
    
    settings_text = [None]
    
    def track_settings(resp):
        url = resp.url
        if 'arkoselabs' in url and 'settings' in url:
            try:
                body = resp.text()
                settings_text[0] = body
                print(f"[SETTINGS] Full body ({len(body)} chars):", flush=True)
                print(body[:1000], flush=True)
                print("...", flush=True)
            except Exception as e:
                print(f"[SETTINGS] Error: {e}", flush=True)
    
    page.on("response", track_settings)
    
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
    
    for i in range(15):
        if page.evaluate("document.getElementById('arkose-0') ? true : false"):
            print(f"[+] arkose-0 at {i}s", flush=True)
            break
        time.sleep(0.5)
    
    if chal_meta_b64:
        original_meta = json.loads(base64.b64decode(chal_meta_b64).decode())
        modified_meta = original_meta.copy()
        if 'sharedParameters' in modified_meta:
            modified_meta['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
            modified_meta['sharedParameters']['renderNativeChallenge'] = True
        new_meta_b64 = base64.b64encode(json.dumps(modified_meta).encode()).decode()
        chal_id = original_meta.get('challengeId', 'generic-challenge')
        chal_type = original_meta.get('challengeType', 'proofofwork')
        
        print(f"[*] Triggering enforcement...", flush=True)
        page.evaluate("""(args) => {
            const script = document.createElement('script');
            script.setAttribute('data-rblx-challenge', args.chalId);
            script.setAttribute('data-rblx-challenge-type', args.chalType);
            script.setAttribute('data-rblx-challenge-metadata', args.metaB64);
            document.head.appendChild(script);
            if (typeof window.PX?.setChallenge === 'function') {
                window.PX.setChallenge(JSON.parse(atob(args.metaB64)));
            }
        }""", {'metaB64': new_meta_b64, 'chalId': chal_id, 'chalType': chal_type})
    
    time.sleep(10)
    
    if settings_text[0] is None:
        print("[-] No settings response captured", flush=True)
    else:
        print(f"\n=== Full settings body ===", flush=True)
        print(settings_text[0], flush=True)
    
    time.sleep(5)
    browser.close()
