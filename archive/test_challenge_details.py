"""Patched PX + capture auth challenge details."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")
patched = patched.replace("new EvalError", "new Error")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    auth_details = []
    
    def track(r):
        url = r.url
        if 'auth.roblox' in url and '/v2/login' in url:
            headers = dict(r.headers)
            auth_details.append({"status": r.status, "headers": headers})
            if r.status == 403:
                chal_type = headers.get('rblx-challenge-type', 'N/A')
                chal_id = headers.get('rblx-challenge-id', 'N/A')
                chal_meta_b64 = headers.get('rblx-challenge-metadata', '')
                print(f"[+] 403: type={chal_type} id={chal_id[:30]}...", flush=True)
                if chal_meta_b64:
                    try:
                        pad = len(chal_meta_b64) % 4
                        if pad:
                            chal_meta_b64 += '=' * (4 - pad)
                        meta = json.loads(base64.b64decode(chal_meta_b64))
                        print(f"[+] Challenge metadata keys: {list(meta.keys())}", flush=True)
                        print(f"[+] eligibleMethods: {meta.get('eligibleMethods', 'NOT FOUND')}", flush=True)
                        print(f"[+] sharedParameters: {meta.get('sharedParameters', {})}", flush=True)
                        print(f"[+] sessionId: {meta.get('sessionId', 'N/A')[:20]}...", flush=True)
                    except Exception as e:
                        print(f"[-] Decode error: {e}", flush=True)
    
    page.on("response", track)
    
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
    page.click("#login-button", timeout=5000)
    time.sleep(3)
    
    print(f"[*] Auth details captured: {len(auth_details)}", flush=True)
    
    page.screenshot(path="challenge_captured.png")
    input("Enter...")
    browser.close()
