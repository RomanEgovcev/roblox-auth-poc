"""Try all click methods to trigger login."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Track network
    auth_reqs = []
    page.on("response", lambda r: auth_reqs.append({"url": r.url[:150], "status": r.status}) if 'auth.roblox' in r.url else None)
    
    # Method 1: page.click - real mouse
    print("[1] Trying page.click...", flush=True)
    try:
        page.click("#login-button", timeout=5000)
        time.sleep(3)
        print(f"  Auth: {[r for r in auth_reqs if 'auth.roblox' in r['url']]}", flush=True)
    except Exception as e:
        print(f"  Failed: {e}", flush=True)
    
    # Check if we need to re-login
    if not auth_reqs:
        page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
        time.sleep(6)
        page.fill("input[name='username']", "testuser123")
        page.fill("input[name='password']", "wrongpass123!")
        
        # Method 2: dispatchEvent on button
        print("[2] Trying dispatchEvent...", flush=True)
        page.evaluate("""() => {
            const btn = document.querySelector('#login-button');
            if (btn) btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
        }""")
        time.sleep(3)
        print(f"  Auth: {[r for r in auth_reqs if 'auth.roblox' in r['url']]}", flush=True)
    
    if not auth_reqs:
        page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
        time.sleep(6)
        page.fill("input[name='username']", "testuser123")
        page.fill("input[name='password']", "wrongpass123!")
        
        # Method 3: Submit the login form
        print("[3] Trying form submit...", flush=True)
        login_forms = page.evaluate("""() => {
            const forms = document.querySelectorAll('form');
            return Array.from(forms).map(f => ({action: f.action, method: f.method, id: f.id}));
        }""")
        print(f"  Forms: {login_forms}", flush=True)
        
        # Try submitting first form
        page.evaluate("""() => {
            const form = document.querySelector('form');
            if (form) form.submit();
        }""")
        time.sleep(3)
        print(f"  Auth: {[r for r in auth_reqs if 'auth.roblox' in r['url']]}", flush=True)
        print(f"  URL: {page.url[:150]}", flush=True)
    
    if not auth_reqs:
        page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
        time.sleep(6)
        page.fill("input[name='username']", "testuser123")
        page.fill("input[name='password']", "wrongpass123!")
        
        # Method 4: Raw fetch
        print("[4] Trying raw fetch...", flush=True)
        result = page.evaluate("""async () => {
            try {
                const resp = await fetch('https://auth.roblox.com/v2/login', {
                    method: 'POST',
                    credentials: 'include',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        ctype: 'Username',
                        cvalue: 'testuser123',
                        password: 'wrongpass123!'
                    })
                });
                return {status: resp.status, text: await resp.text().then(t => t.substring(0, 500)).catch(e => 'err')};
            } catch(e) {return {error: e.message};}
        }""")
        print(f"  Result: {json.dumps(result, indent=2)[:500]}", flush=True)
    
    # Console log
    print(f"\nAll auth: {auth_reqs}", flush=True)
    
    input("Done, check...")
    browser.close()
