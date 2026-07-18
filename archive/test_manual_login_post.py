"""Manual login POST with proper FormData construction to trigger PX."""
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
        if any(x in r.url for x in ['auth.roblox.com', 'arkoselabs.roblox.com', 'client.px-cloud']):
            all_resp.append({'t': time.time(), 's': r.status, 'u': r.url[:200]})
    page.on("response", log_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Construct the login POST manually
    print("[1] Constructing login POST...", flush=True)
    result = page.evaluate("""async () => {
        try {
            const fd = new FormData();
            fd.append('username', document.querySelector('input[name="username"]').value);
            fd.append('password', document.querySelector('input[name="password"]').value);
            // Add ctoken if present
            const ctoken = document.querySelector('input[name="ctoken"]');
            if (ctoken) fd.append('ctoken', ctoken.value);
            
            console.log('Sending login POST with:', Array.from(fd.entries()));
            
            const resp = await fetch('/v2/login', {
                method: 'POST',
                body: fd,
                credentials: 'include',
                headers: {
                    'Accept': 'application/json, text/plain, */*',
                }
            });
            
            const text = await resp.text();
            const headers = {};
            resp.headers.forEach((v, k) => {
                if (k.includes('rblx') || k.includes('challenge') || k === 'content-type') headers[k] = v;
            });
            
            console.log('Login response:', resp.status, text.substring(0, 200));
            
            return {
                status: resp.status,
                headers: JSON.stringify(headers).substring(0, 400),
                bodyLen: text.length,
                bodyPreview: text.substring(0, 200),
            };
        } catch(e) {
            console.error('Login error:', e);
            return {error: e.message, stack: e.stack?.substring(0, 200)};
        }
    }""")
    print(f"  Login result: {json.dumps(result)[:500]}", flush=True)
    
    # Wait for enforcement to appear (PX should intercept the 403)
    print("[2] Waiting 15s for enforcement...", flush=True)
    enf = None
    for i in range(30):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf = f
                break
        if enf:
            print(f"  [+] Enforcement at {i*0.5:.0f}s!", flush=True)
            break
        time.sleep(0.5)
    
    if enf:
        print(f"      {enf.url[:120]}", flush=True)
        time.sleep(3)
        
        # Wait for game-core
        gc = None
        for i in range(20):
            for f in page.frames:
                if 'game-core' in f.url:
                    gc = f
                    break
            if gc:
                print(f"  [+] Game-core at {i*0.5:.0f}s!", flush=True)
                break
            time.sleep(0.5)
        
        if gc:
            time.sleep(3)
            state = gc.evaluate("""() => ({
                imgs: document.querySelectorAll('img').length,
                bodyLen: document.body?.innerHTML?.length || 0,
                bodyPreview: document.body?.innerHTML?.substring(0, 500) || '',
            })""")
            print(f"  GC: {json.dumps(state)[:600]}", flush=True)
    
    print(f"\n=== Key responses ===", flush=True)
    for r in all_resp[-15:]:
        print(f"  [t={r['t']-time.time():.0f}s {r['s']}] {r['u']}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
