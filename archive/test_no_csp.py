"""Remove CSP to allow challenge module to work."""
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
    
    # Strip CSP from all responses
    page.on("response", lambda r: None)  # placeholder
    
    # Use route to strip CSP headers
    def no_csp(route):
        response = page.request.fetch(route.request)
        headers = dict(response.headers)
        # Remove CSP-related headers
        headers.pop('content-security-policy', None)
        headers.pop('content-security-policy-report-only', None)
        headers.pop('x-content-security-policy', None)
        headers.pop('x-webkit-csp', None)
        route.fulfill(
            status=response.status,
            headers=headers,
            body=response.body()
        )
    
    page.route("**/*", no_csp)
    
    all_req = []
    page.on("request", lambda r: all_req.append({"u": r.url[:150], "m": r.method}))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    page.fill('#login-username', USER)
    page.fill('#login-password', PASS)
    time.sleep(1)
    
    page.click('.login-button', timeout=5000)
    print("Clicked!", flush=True)
    
    # Monitor for 30 seconds
    for i in range(30):
        time.sleep(1)
        state = page.evaluate("""() => {
            const chall = document.querySelector('[class*="generic-challenge"]');
            return {
                url: window.location.href.substring(0, 80),
                hasChallenge: chall !== null,
                challVisible: chall ? chall.offsetParent !== null : false,
                challHTML: chall ? chall.innerHTML.substring(0, 300) : '',
                errors: Array.from(document.querySelectorAll('[class*="alert"], [class*="error"]')).filter(e => e.offsetParent !== null).map(e => e.textContent.trim().substring(0, 80)).filter(Boolean),
            };
        }""")
        if state['hasChallenge'] or '/home' in state['url']:
            print(f"\n[{i+1}s] {json.dumps(state, indent=2)}", flush=True)
            break
        if i >= 5 and i % 5 == 0:
            print(f"  [{i+1}s] waiting... errors={state['errors']}", flush=True)
    
    print(f"\nFinal URL: {page.url}", flush=True)
    
    # Check auth POSTs
    auth_posts = [r for r in all_req if 'auth.roblox.com' in r['u'] and r['m'] == 'POST']
    print(f"Auth POSTs ({len(auth_posts)}):", flush=True)
    for r in auth_posts:
        print(f"  {r['u']}", flush=True)
    
    time.sleep(2)
    browser.close()
