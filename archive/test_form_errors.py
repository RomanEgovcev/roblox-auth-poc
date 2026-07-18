"""Check form validation and errors after click."""
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
    
    all_req = []
    page.on("request", lambda r: all_req.append({"u": r.url[:150], "m": r.method}))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    page.fill('#login-username', USER)
    page.fill('#login-password', PASS)
    time.sleep(1)
    
    page.click('.login-button', timeout=5000)
    print("Clicked!", flush=True)
    
    # Wait longer and poll for changes
    for i in range(20):
        time.sleep(1)
        state = page.evaluate("""() => {
            // Check for error messages
            const errors = [];
            document.querySelectorAll('[class*="error"], [class*="alert"], [class*="message"]').forEach(el => {
                if (el.offsetParent !== null && el.textContent.trim()) {
                    errors.push(el.textContent.trim().substring(0, 100));
                }
            });
            // Check for challenge container
            const chall = document.querySelector('[class*="generic-challenge"]');
            // Check URL
            return {
                url: window.location.href.substring(0, 80),
                errors: errors,
                hasChallenge: chall !== null,
                challVisible: chall ? chall.offsetParent !== null : false,
                challHTML: chall ? chall.innerHTML.substring(0, 200) : '',
            };
        }""")
        if state['hasChallenge'] or state['errors'] or '/home' in state['url'] or 'home' in state['url']:
            print(f"\n[{i+1}s] {json.dumps(state, indent=2)}", flush=True)
            break
        if i == 19:
            print(f"\n[{i+1}s] Timeout - no challenge or errors", flush=True)
            print(f"  Final state: {json.dumps(state)}", flush=True)
    
    # Show all POSTs to auth
    auth_posts = [r for r in all_req if 'auth.roblox.com' in r['u'] and r['m'] == 'POST']
    print(f"\nAuth POSTs ({len(auth_posts)}):", flush=True)
    for r in auth_posts:
        print(f"  {r['u']}", flush=True)
    
    print(f"\nFinal URL: {page.url}", flush=True)
    
    time.sleep(2)
    browser.close()
