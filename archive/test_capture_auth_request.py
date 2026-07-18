"""Capture exact auth request from page to replicate it."""
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
    
    auth_request = {}
    
    def capture_req(req):
        if 'auth.roblox.com' in req.url and '/v2/login' in req.url and req.method == 'POST':
            auth_request['url'] = req.url
            auth_request['method'] = req.method
            auth_request['headers'] = dict(req.headers)
            # Can't read body from request easily in sync API
            print(f"[*] Auth request captured!", flush=True)
            print(f"  URL: {req.url}", flush=True)
            print(f"  Headers: {json.dumps(dict(req.headers), indent=2)[:500]}", flush=True)
    
    page.on("request", capture_req)
    
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
    
    with page.expect_response(
        lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
        timeout=15000
    ) as response_info:
        page.click("#login-button", timeout=5000)
    
    resp = response_info.value
    print(f"[+] Auth: {resp.status}", flush=True)
    
    # Try to capture request body via page.evaluate
    body_info = page.evaluate("""() => {
        // Look for recent fetch calls in performance API
        const entries = performance.getEntriesByType('resource');
        const authEntry = entries.find(e => e.name.includes('auth.roblox.com') && e.name.includes('login'));
        if (authEntry) {
            return {
                name: authEntry.name.substring(0, 100),
                duration: authEntry.duration,
                initiatorType: authEntry.initiatorType,
                transferSize: authEntry.transferSize
            };
        }
        return null;
    }""")
    print(f"[*] Performance API: {body_info}", flush=True)
    
    time.sleep(5)
    browser.close()
