"""Direct approach: create arkose script manually to start API flow."""
import os, time, json, base64, sys

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

PUBLIC_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"
ENF_HASH = "504897d1cd342e063d4f67d90600cf04"

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script.replace('new Function("return this")()', "(window||self||globalThis)")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Track ALL responses for Arkose
    arkose_resp = []
    def track_resp(response):
        url = response.url
        if 'arkoselabs.roblox.com' not in url:
            return
        arkose_resp.append({"url": url[:200], "status": response.status})
    page.on("response", track_resp)
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        resp = response_info.value
        print(f"[+] Auth: {resp.status}", flush=True)
    except Exception as e:
        print(f"[-] Auth: {e}", flush=True)
    
    # ===== DIRECT ARKOSE SCRIPT CREATION =====
    print("\n[*] Directly injecting Arkose script...", flush=True)
    
    # Create the div container and script tag
    page.evaluate("""(pk) => {
        // Create arkose container div
        const div = document.createElement('div');
        div.id = 'arkose-0';
        document.body.appendChild(div);
        
        // Create setup callback
        window.setupEnforcement0 = function() {
            console.log('setupEnforcement0 called');
        };
        
        // Create the arkose script tag (same as what Challenge.js creates)
        const script = document.createElement('script');
        script.id = 'arkose-script-' + pk;
        script.type = 'text/javascript';
        script.src = '//arkoselabs.roblox.com/v2/' + pk + '/api.js';
        script.setAttribute('data-callback', 'setupEnforcement0');
        script.async = true;
        script.defer = true;
        document.body.appendChild(script);
        
        return 'script created: ' + script.src;
    }""", PUBLIC_KEY)
    
    # ===== WAIT and monitor =====
    print("[*] Waiting for Arkose API calls (30s)...", flush=True)
    for i in range(60):
        new_resp = [r for r in arkose_resp if not r.get('_p')]
        for r in new_resp:
            r['_p'] = True
            print(f"  [{r['status']}] {r['url'][:140]}", flush=True)
        
        if i % 10 == 0 and i > 0:
            # Check DOM
            dom = page.evaluate("""(pk) => ({
                arkose0: document.getElementById('arkose-0')?.innerHTML?.substring(0, 200) || 'empty',
                scripts: document.querySelectorAll('script[id^=arkose-script]').length,
                iframes: document.querySelectorAll('#arkose-0 iframe').length,
                body_iframes: document.querySelectorAll('iframe').length,
            })""", PUBLIC_KEY)
            print(f"  [{i*0.5:.0f}s] DOM: {json.dumps(dom)[:400]}", flush=True)
        
        time.sleep(0.5)
    
    print(f"\n=== Arkose responses: {len(arkose_resp)} ===", flush=True)
    for r in arkose_resp:
        print(f"  [{r['status']}] {r['url'][:150]}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    page.screenshot(path="arkose_direct_script.png")
    time.sleep(5)
    browser.close()
