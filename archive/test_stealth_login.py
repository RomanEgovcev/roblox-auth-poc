"""Patched PX + stealth measures for auth."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")
patched = patched.replace("new EvalError", "new Error")

# Stealth: override navigator.webdriver and add Chrome runtime
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
// Override chrome.runtime if not present
if (!window.chrome) window.chrome = {};
if (!chrome.runtime) chrome.runtime = {};
"""

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=[
            '--disable-blink-features=AutomationControlled',
        ]
    )
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080},
        locale='en-US',
    )
    page = context.new_page()
    
    # Apply stealth
    page.add_init_script(STEALTH_JS)
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    print("[*] Page loaded, waiting 8s...", flush=True)
    time.sleep(8)
    
    # Check for login form
    has_username = page.locator("input[name='username']").count()
    has_password = page.locator("input[name='password']").count()
    print(f"[*] Login form: username={has_username}, password={has_password}", flush=True)
    
    if has_username:
        page.fill("input[name='username']", "testuser123")
        page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            if has_username:
                page.click("#login-button", timeout=5000)
            else:
                # Try alternative login methods
                page.evaluate("""() => {
                    document.querySelector('#login-button')?.click();
                }""")
        
        resp = response_info.value
        print(f"[+] Auth response: {resp.status}", flush=True)
        
        headers = dict(resp.headers)
        chal_type = headers.get('rblx-challenge-type', 'N/A')
        chal_id = headers.get('rblx-challenge-id', 'N/A')
        chal_meta_b64 = headers.get('rblx-challenge-metadata', '')
        print(f"[+] Type: {chal_type}, ID: {chal_id[:30] if chal_id != 'N/A' else 'N/A'}...", flush=True)
        
        if chal_meta_b64:
            try:
                pad = len(chal_meta_b64) % 4
                if pad:
                    chal_meta_b64 += '=' * (4 - pad)
                meta = json.loads(base64.b64decode(chal_meta_b64))
                sp = meta.get('sharedParameters', {})
                print(f"[+] eligibleMethods: {sp.get('eligibleMethods', 'N/A')}", flush=True)
                print(f"[+] sessionId: {meta.get('sessionId', '')[:20]}...", flush=True)
                print(f"[+] renderNative: {sp.get('renderNativeChallenge', 'N/A')}", flush=True)
                
                # Print full sharedParameters
                print(f"[+] full sharedParams: {json.dumps(sp)[:500]}", flush=True)
            except Exception as e:
                print(f"[-] Decode error: {e}", flush=True)
        
        # Check webdriver detection
        wd = page.evaluate("navigator.webdriver")
        print(f"[+] navigator.webdriver: {wd}", flush=True)
        
    except Exception as e:
        print(f"[-] No auth response: {e}", flush=True)
    
    page.screenshot(path="stealth_login.png")
    print("[*] Done, waiting 15s...", flush=True)
    time.sleep(15)
    browser.close()
