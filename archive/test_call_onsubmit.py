"""Call onFormSubmit directly and monitor requests."""
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
    
    # Track login requests
    login_requests = []
    def track(req):
        if 'auth.roblox.com/v2/login' in req.url and req.method == 'POST':
            login_requests.append({'url': req.url, 'method': req.method, 'headers': dict(req.headers), 'postData': req.post_data})
    page.on('request', track)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    
    page.fill("#login-username", USER)
    page.fill("#login-password", PASS)
    time.sleep(0.5)
    
    # Call onFormSubmit directly
    result = page.evaluate("""async () => {
        const btn = document.querySelector('#login-button');
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        let fiber = btn[fiberKey];
        for (let i = 0; i < 6 && fiber; i++) fiber = fiber.return;
        
        if (!fiber || fiber.tag !== 1) return {error: 'no class component'};
        
        const instance = fiber.stateNode;
        const props = instance.props;
        
        if (typeof props.onFormSubmit !== 'function') return {error: 'no onFormSubmit'};
        
        try {
            console.log('Calling onFormSubmit...');
            const ret = props.onFormSubmit();
            console.log('onFormSubmit returned:', ret);
            return {called: true, returnValue: String(ret), returnType: typeof ret};
        } catch(e) {
            return {error: e.message, stack: e.stack};
        }
    }""")
    print(f"onFormSubmit call:", flush=True)
    for k, v in result.items():
        print(f"  {k}: {v}", flush=True)
    
    time.sleep(3)
    
    print(f"\nLogin requests detected: {len(login_requests)}", flush=True)
    for r in login_requests:
        print(f"  POST {r['url']}", flush=True)
        print(f"  Headers: {json.dumps({k:v for k,v in r['headers'].items() if k in ('x-csrf-token', 'content-type')}, indent=2)}", flush=True)
        if r['postData']:
            print(f"  Body: {r['postData'][:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
