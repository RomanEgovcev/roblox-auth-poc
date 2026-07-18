"""
Test monkey-patching cryptoUtil.generateSecureAuthIntentV2 to fix qr().
"""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    requests = []
    def handle_route(route):
        if "/v2/login" in route.request.url and route.request.method == "POST":
            print(f"  INTERCEPTED POST to /v2/login", flush=True)
            h = dict(route.request.headers)
            print(f"  Has CSRF: {'x-csrf-token' in h}", flush=True)
            requests.append(route.request)
        route.continue_()
    
    page.route("**/*", handle_route)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    print("Page loaded", flush=True)
    
    # Fill credentials
    page.fill('input[name="username"]', "testuser123")
    page.fill('input[name="password"]', "TestPassword123!")
    time.sleep(1)
    
    # Try to find and patch generateSecureAuthIntentV2
    result = page.evaluate("""() => {
        const tryPatch = (root, path) => {
            let obj = root;
            for (const key of path) {
                if (obj && obj[key]) obj = obj[key];
                else return null;
            }
            if (typeof obj.generateSecureAuthIntentV2 === 'function') {
                obj.generateSecureAuthIntentV2 = function() { return Promise.resolve(''); };
                return 'patched via ' + path.join('.');
            }
            return null;
        };
        
        const paths = [
            ['Roblox', 'coreServices', 'cryptoUtil'],
            ['Roblox', 'CoreServices', 'cryptoUtil'],
            ['Roblox', 'cryptoUtil'],
        ];
        
        for (const p of paths) {
            const r = tryPatch(window, p);
            if (r) return r;
        }
        
        // Search deeper
        const results = [];
        for (const key in window.Roblox || {}) {
            try {
                const obj = window.Roblox[key];
                if (obj && obj.cryptoUtil && typeof obj.cryptoUtil.generateSecureAuthIntentV2 === 'function') {
                    obj.cryptoUtil.generateSecureAuthIntentV2 = function() { return Promise.resolve(''); };
                    results.push('patched via Roblox.' + key + '.cryptoUtil');
                }
            } catch(e) {}
        }
        return results.length > 0 ? results.join(', ') : 'not found anywhere';
    }""")
    print(f"Patch result: {result}", flush=True)
    
    # Click login button
    print("Clicking login...", flush=True)
    page.click('button[type="submit"]')
    time.sleep(5)
    
    print(f"URL: {page.url}", flush=True)
    print(f"Requests: {len(requests)}", flush=True)
    for i, req in enumerate(requests):
        print(f"  [{i}] {req.method} {req.url}", flush=True)
    
    time.sleep(3)
    browser.close()
