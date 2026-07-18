"""Force auth 403 by calling /v2/login directly, then process PX challenge."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    all_resp = []
    def log_resp(r):
        if any(x in r.url for x in ['auth.roblox.com', 'arkoselabs.roblox.com', 'client.px-cloud', 'px-cloud.net', 'collector-px']):
            all_resp.append({'t': time.time(), 's': r.status, 'u': r.url[:200]})
    page.on("response", log_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Also add a request listener for the login POST
    reqs = []
    page.on("request", lambda r: reqs.append({'url': r.url[:200], 'method': r.method}) if '/v2/login' in r.url else None)
    
    # Fire the login via fetch - this should trigger PX interception
    print("[1] Firing login via fetch (POST /v2/login)...", flush=True)
    result = page.evaluate("""async () => {
        try {
            const fd = new FormData(document.getElementById('login-form'));
            const resp = await fetch('/v2/login', {
                method: 'POST',
                body: fd,
                credentials: 'include',
            });
            const text = await resp.text();
            const headers = {};
            resp.headers.forEach((v, k) => {
                if (k.startsWith('rblx') || k.startsWith('x-') || k === 'content-type') headers[k] = v;
            });
            return {
                status: resp.status,
                headers: Object.entries(headers).slice(0, 10),
                bodyLen: text.length,
                bodyPreview: text.substring(0, 300),
            };
        } catch(e) {
            return {error: e.message, stack: e.stack?.substring(0, 200)};
        }
    }""")
    print(f"  Fetch result: {json.dumps(result)[:500]}", flush=True)
    time.sleep(5)
    
    # Check if enforcement was created
    print("\n[2] Checking for enforcement...", flush=True)
    enf = None
    for i in range(30):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf = f
                break
        if enf:
            break
        time.sleep(0.5)
    
    if enf:
        print(f"  [+] Enforcement: {enf.url[:120]}", flush=True)
        time.sleep(3)
        gc = None
        for i in range(20):
            for f in page.frames:
                if 'game-core' in f.url:
                    gc = f
                    break
            if gc:
                print(f"  [+] Game-core at t={i*0.5:.0f}s!", flush=True)
                break
            time.sleep(0.5)
        
        if gc:
            state = gc.evaluate("""() => ({
                imgs: document.querySelectorAll('img').length,
                bodyLen: document.body?.innerHTML?.length || 0,
            })""")
            print(f"  GC: {json.dumps(state)}", flush=True)
    else:
        print("  No enforcement.", flush=True)
    
    print(f"\n=== Responses ===", flush=True)
    for r in all_resp:
        print(f"  [t={r['t']-time.time():.0f}s {r['s']}] {r['u']}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(5)
    browser.close()
