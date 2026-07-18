"""Inspect PX.setChallenge implementation."""
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
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # First auth click
    print("[*] First login click...", flush=True)
    with page.expect_response(
        lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
        timeout=15000
    ) as response_info:
        page.click("#login-button", timeout=5000)
    
    resp = response_info.value
    print(f"[+] Auth: {resp.status}", flush=True)
    
    # NOW intercept setChallenge to add eligibleMethods
    print("[*] Setting up setChallenge interceptor...", flush=True)
    mod_result = page.evaluate("""() => {
        if (!window.PX || !window.PX.setChallenge) return 'no setChallenge';
        
        const original = window.PX.setChallenge;
        window.PX.setChallenge = function(data) {
            try {
                if (data && data.metadata) {
                    let meta = JSON.parse(atob(data.metadata));
                    let sp = meta.sharedParameters || {};
                    sp.eligibleMethods = ['captcha', 'proofofwork'];
                    sp.renderNativeChallenge = true;
                    meta.sharedParameters = sp;
                    data.metadata = btoa(JSON.stringify(meta));
                    console.log('[PX] Mod: eligibleMethods -> captcha');
                }
            } catch(e) {
                console.log('[PX] Mod error:', e.message);
            }
            return original.call(this, data);
        };
        return 'setChallenge patched';
    }""")
    print(f"[*] {mod_result}", flush=True)
    
    # Re-click login to get a new challenge
    print("[*] Clicking login again...", flush=True)
    
    time.sleep(1)
    
    with page.expect_response(
        lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
        timeout=15000
    ) as response_info:
        page.click("#login-button", timeout=5000)
    
    resp2 = response_info.value
    print(f"[+] Auth2: {resp2.status}", flush=True)
    
    time.sleep(5)
    
    # Check for new frames
    frames = page.frames
    arkose = [f for f in frames if 'arkose' in f.url]
    enforcement = [f for f in frames if 'enforcement' in f.url]
    print(f"Frames: {len(frames)}, arkose: {len(arkose)}, enforcement: {len(enforcement)}", flush=True)
    for f in frames:
        url = f.url[:120]
        if 'roblox' not in url:
            print(f"  {url}", flush=True)
    
    page.screenshot(path="px_inspect.png")
    time.sleep(5)
    browser.close()
