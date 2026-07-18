"""Intercept Arkose API calls without breaking the flow."""
import os, time, json, base64, sys

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
    
    arkose_reqs = []
    
    # Track Arkose responses
    def track_arkose(response):
        url = response.url
        if 'arkoselabs.roblox.com' not in url:
            return
        if url.endswith('.js') or url.endswith('.html') or url.endswith('.css'):
            arkose_reqs.append({'url': url[:200], 'status': response.status, 'body': ''})
        else:
            try:
                body = response.text()
                arkose_reqs.append({'url': url[:200], 'status': response.status, 'body': body[:400]})
            except:
                arkose_reqs.append({'url': url[:200], 'status': response.status, 'body': '(unreadable)'})
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
        browser.close()
        sys.exit(1)
    
    if not chal_meta_b64:
        print("[-] No challenge metadata!", flush=True)
        browser.close()
        sys.exit(1)
    
    original_meta = json.loads(base64.b64decode(chal_meta_b64).decode())
    print(f"[+] Meta: sessionId={original_meta.get('sessionId','?')[:20]}, eligibleMethods={original_meta.get('sharedParameters',{}).get('eligibleMethods')}", flush=True)
    
    # ===== MANUAL TRIGGER =====
    modified_meta = original_meta.copy()
    if 'sharedParameters' in modified_meta:
        modified_meta['sharedParameters']['eligibleMethods'] = ['captcha', 'proofofwork']
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
            try { window.PX.setChallenge(JSON.parse(atob(args.metaB64))); }
            catch(e) { console.error('PX.setChallenge error:', e); }
        }
    }""", {'metaB64': new_meta_b64, 'chalId': chal_id, 'chalType': chal_type})
    
    # ===== WAIT and print Arkose API calls =====
    print("[*] Waiting for Arkose API calls (30s)...", flush=True)
    for i in range(60):
        new_calls = [r for r in arkose_reqs if not r.get('_printed')]
        for r in new_calls:
            r['_printed'] = True
            body_preview = r['body'].replace('\n', ' ')[:300]
            print(f"  [{r['status']}] {r['url'][:120]}", flush=True)
            if body_preview and 'html' not in r['url'] and 'js' not in r['url']:
                print(f"    Body: {body_preview}", flush=True)
        
        # Check DOM periodically
        if i % 20 == 0 and i > 0:
            dom = page.evaluate("""() => ({
                arkose0: document.getElementById('arkose-0') ? document.getElementById('arkose-0').innerHTML.substring(0, 200) : 'missing',
                scripts: Array.from(document.querySelectorAll('script[id^=arkose-script]')).map(s => s.src.substring(0, 120)),
                iframes: document.querySelectorAll('#arkose-0 iframe').length,
            })""")
            print(f"  [{i*0.5:.0f}s] DOM: {json.dumps(dom)[:400]}", flush=True)
        
        time.sleep(0.5)
    
    print(f"\n=== Total Arkose calls: {len(arkose_reqs)} ===", flush=True)
    
    page.screenshot(path="arkose_intercepted.png")
    time.sleep(5)
    browser.close()
