"""Try enforcement iframe with auto-generated session."""
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
    
    arkose_resp = []
    def track_resp(response):
        url = response.url
        if 'arkoselabs.roblox.com' in url:
            arkose_resp.append({"url": url[:250], "status": response.status})
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
    
    # ===== CREATE ENFORCEMENT IFRAME =====
    # Try with empty session token (enforcement may generate its own)
    print("\n[*] Creating enforcement iframe (empty session token)...", flush=True)
    
    enforce_url = f"https://arkoselabs.roblox.com/v2/4.4.2/enforcement.{ENF_HASH}.html#{PUBLIC_KEY}&"
    
    page.evaluate("""(url) => {
        const div = document.createElement('div');
        div.id = 'arkose-0';
        div.style.width = '600px';
        div.style.height = '500px';
        div.style.border = '2px solid red';
        document.body.prepend(div);
        
        const iframe = document.createElement('iframe');
        iframe.src = url;
        iframe.style.width = '100%';
        iframe.style.height = '100%';
        iframe.style.border = 'none';
        div.appendChild(iframe);
        return 'iframe created: ' + url;
    }""", enforce_url)
    
    # ===== WAIT for enforcement or game-core =====
    print("[*] Waiting for enforcement activities (120s)...", flush=True)
    
    enf_frame = None
    for i in range(240):
        # Check Arkose responses
        new_resp = [r for r in arkose_resp if not r.get('_p')]
        for r in new_resp:
            r['_p'] = True
            print(f"  [{r['status']}] {r['url'][:150]}", flush=True)
        
        # Check for enforcement frame
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                break
        
        if i % 30 == 0 and i > 0:
            dom = page.evaluate("""() => ({
                iframes: document.querySelectorAll('#arkose-0 iframe').length,
                src: document.querySelector('#arkose-0 iframe')?.src?.substring(0, 200) || '',
            })""")
            print(f"  [{i*0.5:.0f}s] DOM: {json.dumps(dom)[:300]}", flush=True)
            print(f"    Frames: {[(f.url[:120]) for f in page.frames]}", flush=True)
        
        time.sleep(0.5)
    
    print(f"\n=== Total Arkose responses: {len(arkose_resp)} ===", flush=True)
    for r in arkose_resp:
        print(f"  [{r['status']}] {r['url'][:200]}", flush=True)
    
    page.screenshot(path="enforcement_empty_token.png")
    time.sleep(10)
    browser.close()
