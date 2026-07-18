"""Trigger enforcement, then submit via fetch through PX."""
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
        if any(x in r.url for x in ['/v2/login', '/fc/', 'arkoselabs', 'arkoselabs/']):
            all_resp.append({'t': f"{time.time():.0f}", 's': r.status, 'u': r.url[:200]})
    page.on("response", log_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Trigger enforcement via dispatchEvent click with priming
    print("[1] Triggering enforcement...", flush=True)
    page.evaluate("""(() => {
        const btn = document.getElementById('login-button');
        if (!btn) return;
        for (let i = 0; i < 3; i++)
            btn.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',bubbles:true}));
        btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
    })()""")
    
    enf = None
    for i in range(20):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf = f
                break
        if enf:
            break
        time.sleep(0.5)
    
    if not enf:
        print("  No enforcement!", flush=True)
        browser.close()
        exit()
    
    print(f"  Enforcement at t={time.time():.0f}s: {enf.url[:100]}", flush=True)
    time.sleep(3)
    
    # Now submit via fetch
    print("[2] Submitting login via fetch...", flush=True)
    result = page.evaluate("""async () => {
        try {
            const fd = new FormData(document.getElementById('login-form'));
            const resp = await fetch('/v2/login', {method:'POST', body:fd, credentials:'include'});
            const text = await resp.text();
            return {
                status: resp.status,
                headers: Array.from(resp.headers.entries()).filter(h => h[0].startsWith('rblx') || h[0].startsWith('x-')).slice(0, 15),
                text: text.substring(0, 300),
            };
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"  Result: {json.dumps(result)[:500]}", flush=True)
    
    # Wait for game-core images
    print("[3] Waiting 20s for game-core + challenge...", flush=True)
    gc, vt = None, None
    for i in range(40):
        for f in page.frames:
            if 'game-core' in f.url:
                gc = f
        if enf:
            try:
                vt = enf.evaluate("""() => document.getElementById('verification-token')?.value || null""", timeout=3000)
            except:
                pass
        
        if gc:
            try:
                imgs = gc.evaluate("document.querySelectorAll('img').length", timeout=3000)
                if imgs > 0:
                    print(f"  [+] Challenge images at {i*0.5:.0f}s!", flush=True)
            except:
                pass
        
        if vt:
            print(f"  [+] Verification token at {i*0.5:.0f}s!", flush=True)
        
        if gc and vt:
            break
        time.sleep(0.5)
    
    if gc:
        state = gc.evaluate("""() => ({
            imgs: document.querySelectorAll('img').length,
            bodyLen: document.body?.innerHTML?.length || 0,
        })""")
        print(f"  GC: {json.dumps(state)}", flush=True)
    
    print(f"\n  VT: {vt[:100] if vt else 'None'}", flush=True)
    
    print(f"\n=== Key responses ===", flush=True)
    for r in all_resp:
        print(f"  [t={r['t']}s {r['s']}] {r['u']}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(5)
    browser.close()
