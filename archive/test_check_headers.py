"""Check ALL auth 403 response headers for Arkose session info."""
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
    
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        resp = response_info.value
        print(f"[+] Auth: {resp.status}", flush=True)
        print(f"\n=== ALL Response Headers ===", flush=True)
        for k, v in resp.headers.items():
            print(f"  {k}: {v[:200]}", flush=True)
        
        # Check rblx-challenge-metadata
        chal_meta_b64 = None
        for k, v in resp.headers.items():
            if k.lower() == 'rblx-challenge-metadata':
                chal_meta_b64 = v
                break
        
        if chal_meta_b64:
            meta = json.loads(base64.b64decode(chal_meta_b64).decode())
            print(f"\n=== Challenge metadata ===", flush=True)
            print(json.dumps(meta, indent=2), flush=True)
        
    except Exception as e:
        print(f"[-] Auth: {e}", flush=True)
    
    page.screenshot(path="auth_403_headers.png")
    time.sleep(5)
    browser.close()
