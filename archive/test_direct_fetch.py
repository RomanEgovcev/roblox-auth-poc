"""Bypass React form delay - call login fetch directly from page context."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    t0 = [None]
    
    def on_req(req):
        if t0[0] is None:
            return
        dt = time.time() - t0[0]
        if any(x in req.url for x in ("/v2/login", "pow-puzzle", "challenge/v1", "px-cloud", "worker-resources", "main.min")):
            print(f"[{dt:5.1f}s] {req.method} {req.url[:120]}", flush=True)
    
    page.on("request", on_req)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    # Get CSRF token from page
    csrf = page.evaluate("() => document.querySelector('meta[name=\"csrf-token\"]')?.content || ''")
    print(f"CSRF: {csrf[:20] if csrf else 'NONE'}", flush=True)
    
    # Also get the authentication intent key
    sai = page.evaluate("""() => {
        try {
            return window.CoreRobloxUtilities?.cryptoUtil?.generateSecureAuthIntentV2?.();
        } catch(e) { return null; }
    }""")
    print(f"SAI: {'yes' if sai else 'no'}", flush=True)
    
    # Try calling login via page context fetch (PX-wrapped)
    result = page.evaluate("""(csrf) => {
        const body = JSON.stringify({
            ctype: 'Username',
            username: 'testuser123',
            password: 'TestPassword123!'
        });
        return fetch('https://auth.roblox.com/v2/login?urlLocale=en_us', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json;charset=UTF-8',
                'X-CSRF-TOKEN': csrf
            },
            body: body
        }).then(r => {
            console.log('LOGIN_FETCH_DONE', r.status);
            return { status: r.status, headers: Object.fromEntries(r.headers.entries()) };
        }).catch(e => ({ error: e.message }));
    }""", csrf)
    
    print(f"Login fetch result: {result}", flush=True)
    
    time.sleep(20)
    
    print(f"\nDone", flush=True)
    browser.close()
