"""Deep investigation: capture gt2 payload and check enforcement frame."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

gt2_requests = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    def log_resp(r):
        url = r.url
        if 'arkoselabs' in url:
            status = r.status
            short = url[40:180]
            if 'gt2' in url:
                print(f"  [{status}] GT2: {short}", flush=True)
                gt2_requests.append({'url': url, 'status': status})
            elif '/fc/' in url and 'gt2' not in url:
                pass  # skip fingerprints/etc
            else:
                print(f"  [{status}] {short}", flush=True)
    
    page.on("response", log_resp)
    page.on("request", lambda r: print(f"  >> {r.url[40:180]}", flush=True) if 'fc/gt2' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Load api.js ourselves with callback
    print("\n[1] Loading api.js...", flush=True)
    loaded = page.evaluate("""() => {
        return new Promise((resolve) => {
            window.__arkCB = function(api) {
                window.__arkApi = api;
                console.log('API received, methods:', Object.keys(api).join(','));
                resolve(true);
            };
            const s = document.createElement('script');
            s.src = 'https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js';
            s.setAttribute('data-callback', '__arkCB');
            document.head.appendChild(s);
            setTimeout(() => resolve(false), 15000);
        });
    }""")
    print(f"  Loaded: {loaded}", flush=True)
    
    if not loaded:
        print("  API load failed!", flush=True)
        browser.close()
        exit()
    
    # setConfig
    print("\n[2] setConfig...", flush=True)
    page.evaluate("""() => {
        window.__arkApi.setConfig({
            publicKey: '476068BF-9607-4799-B53D-966BE98E2B81',
        });
    }""")
    
    # Wait for settings + fingerprints
    time.sleep(8)
    
    # run
    print("\n[3] Calling run()...", flush=True)
    page.evaluate("() => { window.__arkApi.run(); }")
    
    # Watch for gt2, enforcement, game-core
    print("\n[4] Watching for 30s...", flush=True)
    frames_seen = set()
    for i in range(60):
        # Check enforcement iframe contents
        for f in page.frames:
            if f.url not in frames_seen:
                frames_seen.add(f.url)
                if 'enforcement' in f.url or 'game-core' in f.url:
                    print(f"  [+] New frame: {f.url[:200]}", flush=True)
        
        if 'game-core' in ' '.join(f.url for f in page.frames):
            gc_frame = [f for f in page.frames if 'game-core' in f.url][0]
            state = gc_frame.evaluate("""() => ({
                imgs: document.querySelectorAll('img').length,
                bodyLen: document.body?.innerHTML?.length || 0,
            })""")
            print(f"  GC: {json.dumps(state)}", flush=True)
            time.sleep(0.5)
            break
        
        time.sleep(0.5)
    
    # Check enforcement frame state
    enf_frame = None
    for f in page.frames:
        if 'enforcement' in f.url:
            enf_frame = f
            break
    
    if enf_frame:
        enf_state = enf_frame.evaluate("""() => ({
            hash: window.location.hash,
            src: document.querySelector('script[src*=\"enforcement\"]')?.src || '',
            body: document.body?.innerHTML?.substring(0, 500) || '',
        })""")
        print(f"\n  Enforcement state:")
        print(f"    hash: {enf_state['hash']}")
        print(f"    src: {enf_state['src']}")
        print(f"    body: {enf_state['body']}", flush=True)
    
    print(f"\n=== All frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    print(f"\n=== GT2 requests: {json.dumps(gt2_requests)}", flush=True)
    
    time.sleep(3)
    browser.close()
