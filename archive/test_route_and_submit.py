"""Call onFormSubmit with persistent route monitoring."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    login_post_data = []
    
    def handle_login(route):
        if 'auth.roblox.com/v2/login' in route.request.url and route.request.method == 'POST':
            login_post_data.append({
                'headers': dict(route.request.headers),
                'postData': route.request.post_data,
                'url': route.request.url,
            })
        route.continue_()
    
    page.route("**/v2/login", handle_login)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    
    page.fill("#login-username", USER)
    page.fill("#login-password", PASS)
    time.sleep(0.5)
    
    # Call onFormSubmit directly
    result = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        let fiber = btn[fiberKey];
        for (let i = 0; i < 6 && fiber; i++) fiber = fiber.return;
        if (!fiber || fiber.tag !== 1) return 'no class component';
        const instance = fiber.stateNode;
        if (typeof instance.props.onFormSubmit !== 'function') return 'no onFormSubmit';
        instance.props.onFormSubmit();
        return 'called onFormSubmit';
    }""")
    print(f"Result: {result}", flush=True)
    
    # Wait for deferred calls
    for i in range(10):
        time.sleep(1)
        if login_post_data:
            break
        if i == 0:
            # Trigger a React state update to force pending effects
            page.evaluate("""() => {
                // Dispatch a click to trigger any pending effects
                document.querySelector('#login-button')?.dispatchEvent(new Event('click', {bubbles: true}));
            }""")
    
    print(f"\nLogin POSTs detected: {len(login_post_data)}", flush=True)
    for i, d in enumerate(login_post_data):
        print(f"  POST #{i+1}:", flush=True)
        print(f"    URL: {d['url']}", flush=True)
        h = d['headers']
        print(f"    x-csrf-token: {h.get('x-csrf-token', 'N/A')}", flush=True)
        print(f"    content-type: {h.get('content-type', 'N/A')}", flush=True)
        if d['postData']:
            print(f"    body: {d['postData'][:200]}", flush=True)
    
    # If no POST after 10s, try directly calling the API module
    if not login_post_data:
        print(f"\nNo login POST - checking what qr does...", flush=True)
        qrInfo = page.evaluate("""() => {
            // Find qr in the React component's closure by examining the module system
            // The login bundle likely exports a login function
            if (window.Roblox && window.Roblox.__loginFunction) {
                return 'roblox login fn: ' + window.Roblox.__loginFunction.toString().substring(0, 500);
            }
            
            // Look for common login patterns in the page's JS
            const scripts = document.querySelectorAll('script');
            const results = [];
            for (const s of scripts) {
                if (s.src && (s.src.includes('login') || s.src.includes('Login'))) {
                    results.push(s.src.substring(0, 100));
                }
            }
            return {loginScripts: results};
        }""")
        print(f"  {qrInfo}", flush=True)
        
        # Try calling qr directly from the module that contains it
        # The onFormSubmit function is defined in a bundle. Let's find the bundle
        page.evaluate("""async () => {
            // The variable qr is used in the onFormSubmit closure
            // Let's look for the original request function
            // The login API call is likely in a module that's imported
            // Let's check window.__ROBLOX_API__ or similar
            
            // Actually, let's look at all webpack module exports
            if (window.webpackJsonp || window.__webpack_require__) {
                console.log('Webpack found');
            }
            
            // Search common locations
            const possibilities = ['__api', '__ROBLOX_API', 'RobloxApi', 'api', 'http'];
            for (const p of possibilities) {
                if (window[p]) console.log(p, typeof window[p]);
            }
        }""")
    
    time.sleep(3)
    browser.close()
