"""Intercept Arkose API responses for debugging."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script.replace('new Function("return this")()', "(window||self||globalThis)")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    
    arkose_bodies = []
    
    def track_arkose(resp):
        url = resp.url
        if 'arkoselabs' in url:
            if 'settings' in url or 'gt2/public_key' in url:
                try:
                    body = resp.text()
                    arkose_bodies.append({'url': url[:150], 'status': resp.status, 'body': body[:500]})
                except:
                    arkose_bodies.append({'url': url[:150], 'status': resp.status, 'body': '<error>'})
    
    page.on("response", track_arkose)
    
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
    
    chal_meta_b64 = None
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        resp = response_info.value
        for k, v in resp.headers.items():
            if k.lower() == 'rblx-challenge-metadata':
                chal_meta_b64 = v
                break
        print(f"[+] Auth: {resp.status}", flush=True)
    except Exception as e:
        print(f"[-] Auth: {e}", flush=True)
    
    # Wait for arkose container
    for i in range(15):
        if page.evaluate("document.getElementById('arkose-0') ? true : false"):
            print(f"[+] arkose-0 at {i}s", flush=True)
            break
        time.sleep(0.5)
    
    # Verify: check if arkoselabs.roblox.com is actually accessible
    net_test = page.evaluate("""async () => {
        try {
            const r = await fetch('https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/settings');
            return {status: r.status, ok: r.ok, body: await r.text().then(t => t.substring(0, 200))};
        } catch(e) { return {error: e.message}; }
    }""")
    print(f"\n=== Direct fetch test ===", flush=True)
    print(json.dumps(net_test, indent=2), flush=True)
    
    # Trigger enforcement
    if chal_meta_b64:
        original_meta = json.loads(base64.b64decode(chal_meta_b64).decode())
        modified_meta = original_meta.copy()
        if 'sharedParameters' in modified_meta:
            modified_meta['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
            modified_meta['sharedParameters']['renderNativeChallenge'] = True
        new_meta_b64 = base64.b64encode(json.dumps(modified_meta).encode()).decode()
        chal_id = original_meta.get('challengeId', 'generic-challenge')
        chal_type = original_meta.get('challengeType', 'proofofwork')
        
        print(f"\n[*] Triggering enforcement...", flush=True)
        page.evaluate("""(args) => {
            const script = document.createElement('script');
            script.setAttribute('data-rblx-challenge', args.chalId);
            script.setAttribute('data-rblx-challenge-type', args.chalType);
            script.setAttribute('data-rblx-challenge-metadata', args.metaB64);
            document.head.appendChild(script);
            if (typeof window.PX?.setChallenge === 'function') {
                window.PX.setChallenge(JSON.parse(atob(args.metaB64)));
            }
        }""", {'metaB64': new_meta_b64, 'chalId': chal_id, 'chalType': chal_type})
    
    time.sleep(10)
    
    # Print captured Arkose bodies
    print(f"\n=== Arkose API responses ===", flush=True)
    for b in arkose_bodies:
        print(f"  [{b['status']}] {b['url']}", flush=True)
        print(f"    Body: {b['body'][:300]}", flush=True)
    
    # Check enforcement state
    state = page.evaluate("""() => ({
        arkose0_html: document.getElementById('arkose-0')?.innerHTML?.substring(0, 100) || 'empty',
        scripts: Array.from(document.querySelectorAll('script[id^=arkose-script]')).map(s => ({
            id: s.id, src: (s.src || '').substring(0, 150)
        }))
    })""")
    print(f"\n=== State ===", flush=True)
    print(json.dumps(state, indent=2), flush=True)
    
    # Check if there are more Arkose requests coming
    print(f"\n[*] Waiting 20 more seconds for Arkose requests...", flush=True)
    prev_count = len(arkose_bodies)
    for i in range(20):
        time.sleep(1)
        new_count = len(arkose_bodies)
        if new_count > prev_count:
            print(f"  [{i+1}s] New Arkose request! Total: {new_count}", flush=True)
            for b in arkose_bodies[prev_count:]:
                print(f"    [{b['status']}] {b['url']}", flush=True)
            prev_count = new_count
    
    print(f"\n=== All Arkose responses ({len(arkose_bodies)}) ===", flush=True)
    for b in arkose_bodies:
        print(f"  [{b['status']}] {b['url']}", flush=True)
    
    time.sleep(5)
    browser.close()
