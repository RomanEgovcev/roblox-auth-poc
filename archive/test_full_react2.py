"""
Full React login flow - the POST works! PX starts challenge.
Wait long enough for PX to compute and complete the challenge.
"""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("pageerror", lambda err: print(f"[PAGE_ERROR] {err}", flush=True))
    page.on("console", lambda msg: print(f"[CONSOLE] {msg.text[:300]}", flush=True))
    
    # Track responses
    responses = []
    def on_response(resp):
        if "/v2/login" in resp.url:
            print(f"\n[RESPONSE] {resp.status} {resp.url}", flush=True)
            h = resp.headers
            for k, v in h.items():
                if "challenge" in k.lower() or "csrf" in k.lower() or "content" in k.lower():
                    print(f"  {k}: {v[:100]}", flush=True)
            responses.append({"status": resp.status, "url": resp.url, "headers": dict(h)})
    page.on("response", on_response)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    print("Page loaded", flush=True)
    
    # Fill credentials
    page.fill('input[name="username"]', "testuser123")
    page.fill('input[name="password"]', "TestPassword123!")
    time.sleep(1)
    
    # Trigger onFormSubmit via React fiber
    result = page.evaluate("""async () => {
        const root = document.querySelector('#login-base') || 
                     document.querySelector('.login-base-container') || 
                     document.querySelector('[id*=\"login\"]') || 
                     document.getElementById('react-login-web-app') || 
                     document.body;
        
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        if (!key) return 'no fiber key on ' + (root.id || root.className || 'body');
        
        function walkFibers(fiber, depth, cb) {
            if (!fiber || depth > 20) return;
            cb(fiber, depth);
            if (fiber.child) walkFibers(fiber.child, depth + 1, cb);
            if (fiber.sibling) walkFibers(fiber.sibling, depth, cb);
        }
        
        let found = false;
        const rootFiber = root[key];
        
        if (rootFiber) {
            walkFibers(rootFiber, 0, (f, d) => {
                if (f.memoizedProps && f.memoizedProps.onFormSubmit && !found) {
                    console.log('Found onFormSubmit at depth', d, 'tag:', f.tag);
                    found = true;
                    f.memoizedProps.onFormSubmit();
                }
            });
        }
        
        if (!found) {
            // Try the new form - find form submit handler
            const form = document.querySelector('form');
            if (form) {
                form.requestSubmit();
                return 'form submitted directly';
            }
            return 'not found';
        }
        return 'onFormSubmit called';
    }""")
    print(f"Result: {result}", flush=True)
    
    # Wait for challenge to complete (PX solves POW in ~3 seconds + overhead)
    print("\nWaiting for PX to solve challenge...", flush=True)
    for i in range(80):  # 80 seconds max
        time.sleep(1)
        
        # Check URL change (login redirect)
        if "home" in page.url.lower() or "games" in page.url.lower():
            print(f"\n*** LOGIN SUCCESS! Redirected to: {page.url} ***", flush=True)
            break
        
        # Check if challenge modal appeared/disappeared
        if i == 10:
            print("  Still waiting...", flush=True)
    
    print(f"\nFinal URL: {page.url}", flush=True)
    print(f"Responses to /v2/login:", flush=True)
    for r in responses:
        print(f"  {r['status']} {r['url']}", flush=True)
    
    time.sleep(5)
    browser.close()
