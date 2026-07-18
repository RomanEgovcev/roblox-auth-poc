"""Two-step login: get CSRF then retry with proper PX interception."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    def on_req(req):
        if any(x in req.url for x in ("/v2/login", "challenge/v1", "pow-puzzle", "px-cloud", "main.min")):
            print(f"[REQ] {req.method} {req.url[:120]}", flush=True)
        if "/v2/login" in req.url:
            h = dict(req.headers)
            print(f"   headers: csrf={'yes' if h.get('x-csrf-token') else 'no'} px={'yes' if any('px' in k for k in h) else 'no'}", flush=True)
    page.on("request", on_req)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    # Step 1: Get CSRF via fetch (no PX intercept expected)
    csrf1 = page.evaluate("""() => {
        return fetch('https://auth.roblox.com/v2/login?urlLocale=en_us', {
            method: 'POST',
            headers: {'Content-Type': 'application/json;charset=UTF-8'},
            body: '{}'
        }).then(r => { throw new Error('expected 403'); })
        .catch(e => 'err');
    }""")
    print(f"CSRF fetch: {csrf1}", flush=True)
    
    time.sleep(2)
    
    # Step 2: Now try login with the CSRF from response
    result = page.evaluate("""() => {
        return fetch('https://auth.roblox.com/v2/login?urlLocale=en_us', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json;charset=UTF-8',
                'X-CSRF-TOKEN': 'qfL3r35w8byJ'
            },
            body: JSON.stringify({ctype:'Username', username:'testuser123', password:'TestPassword123!'})
        }).then(r => {
            const h = {};
            r.headers.forEach((v,k) => { h[k] = v; });
            return {status: r.status, headers: h, hasChallenge: 'rblx-challenge-id' in h};
        });
    }""")
    print(f"Login result: status={result['status']} hasChallenge={result['hasChallenge']}")
    if result.get('headers'):
        for k, v in result['headers'].items():
            if 'rblx' in k or 'px' in k or 'csrf' in k or 'challenge' in k:
                print(f"  {k}: {v[:40]}", flush=True)
    
    time.sleep(10)
    browser.close()
