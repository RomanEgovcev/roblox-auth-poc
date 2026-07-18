"""Approach 1: Click login WITHOUT patching PX. Try Enter key + dispatchEvent."""
import os, time, json, base64, sys

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Track Arkose responses
    arkose_resp = []
    def track_resp(response):
        url = response.url
        if 'arkoselabs.roblox.com' in url:
            arkose_resp.append(f"[{response.status}] {url[:180]}")
    page.on("response", track_resp)
    
    # Track console errors
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)[:200]))
    
    # NO PX patch - use original PX script
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Trying login methods WITHOUT patching PX...", flush=True)
    
    # Method A: Press Enter in password field
    print("\n  [A] Press Enter in password field...", flush=True)
    try:
        page.keyboard.press("Enter")
        time.sleep(5)
        
        # Check if auth was made
        auth_made = any('auth.roblox.com' in r for r in arkose_resp)
        print(f"  Result: auth_made={auth_made}, arkose_calls={len(arkose_resp)}", flush=True)
    except Exception as e:
        print(f"  Enter error: {e}", flush=True)
    
    # Check state
    dom = page.evaluate("""() => ({
        arkose0: document.getElementById('arkose-0') ? 'exists' : 'missing',
        scripts: document.querySelectorAll('script[id^=arkose-script]').length,
        challengeContainer: document.getElementById('generic-challenge-container-proofofwork') ? 'exists' : 'missing',
    })""")
    print(f"  DOM after Enter: {json.dumps(dom)}", flush=True)
    
    # Method B: dispatchEvent on login button
    if not arkose_resp:
        print("\n  [B] dispatchEvent click...", flush=True)
        page.evaluate("""() => {
            const btn = document.querySelector('#login-button');
            if (btn) {
                btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
            }
        }""")
        time.sleep(5)
        
        # Check
        auth_made = any('auth.roblox.com' in r for r in arkose_resp)
        dom2 = page.evaluate("""() => ({
            arkose0: document.getElementById('arkose-0') ? 'exists' : 'missing',
            scripts: document.querySelectorAll('script[id^=arkose-script]').length,
        })""")
        print(f"  Result: auth_made={auth_made}, DOM={json.dumps(dom2)}", flush=True)
    
    # Method C: native .click()
    if not arkose_resp:
        print("\n  [C] Native .click()...", flush=True)
        page.evaluate("""() => {
            const btn = document.querySelector('#login-button');
            if (btn) btn.click();
        }""")
        time.sleep(5)
        
        auth_made = any('auth.roblox.com' in r for r in arkose_resp)
        dom3 = page.evaluate("""() => ({
            arkose0: document.getElementById('arkose-0') ? 'exists' : 'missing',
            scripts: document.querySelectorAll('script[id^=arkose-script]').length,
        })""")
        print(f"  Result: auth_made={auth_made}, DOM={json.dumps(dom3)}", flush=True)
    
    # Method D: PATCH PX and use page.click (baseline)
    if not arkose_resp:
        print("\n  [D] PATCH PX + page.click (baseline)...", flush=True)
        browser.close()
        
        # Restart with patched PX
        with open("main_min.js", "r", encoding="utf-8") as f:
            px_script = f.read()
        patched = px_script.replace('new Function("return this")()', "(window||self||globalThis)")
        
        browser2 = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        page2 = browser2.new_page()
        page2.set_viewport_size({"width": 1280, "height": 900})
        
        page2.on("response", lambda r: arkose_resp.append(f"[{r.status}] {r.url[:180]}") if 'arkoselabs.roblox.com' in r.url else None)
        
        def intercept(route):
            url = route.request.url
            if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
                route.fulfill(status=200, body=patched, content_type='application/javascript')
            else:
                route.continue_()
        
        page2.route("**/main.min.js", intercept)
        
        page2.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
        time.sleep(8)
        
        page2.fill("input[name='username']", "testuser123")
        page2.fill("input[name='password']", "wrongpass123!")
        
        try:
            page2.click("#login-button", timeout=5000)
            time.sleep(8)
            
            auth_made = any('auth.roblox.com' in r for r in arkose_resp)
            dom4 = page2.evaluate("""() => ({
                arkose0: document.getElementById('arkose-0') ? 'exists' : 'missing',
                scripts: document.querySelectorAll('script[id^=arkose-script]').length,
                error: document.querySelector('.error')?.innerText || '',
            })""")
            print(f"  Result: auth_made={auth_made}, DOM={json.dumps(dom4)}", flush=True)
        except Exception as e:
            print(f"  Click error: {e}", flush=True)
        
        browser2.close()
        page = page2
    
    # ===== SUMMARY =====
    print(f"\n=== Final Arkose responses ({len(arkose_resp)}) ===", flush=True)
    for r in arkose_resp:
        print(f"  {r}", flush=True)
    
    print(f"\n=== Errors ===", flush=True)
    for e in errors[-5:]:
        print(f"  {e}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:150]}", flush=True)
    
    time.sleep(5)
    browser.close()
