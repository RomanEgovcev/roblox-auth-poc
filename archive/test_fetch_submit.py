"""Submit login via fetch through PX override, then extract challenge data."""
import os, time, json, sys, re

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    all_resp = []
    page.on("response", lambda r: all_resp.append({
        't': time.time(), 's': r.status, 'u': r.url[:250]
    }) if '/v2/login' in r.url or '/fc/' in r.url or 'arkoselabs' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(8)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(2)
    
    # Wait for the auth pre-flight 403 to complete
    print("[1] Waiting for pre-flight 403 + enforcement setup...", flush=True)
    time.sleep(15)
    
    # Find enforcement
    enf = None
    for f in page.frames:
        if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
            enf = f
            break
    
    if not enf:
        print("  No enforcement. Triggering via dispatchEvent click...", flush=True)
        page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            if (btn) btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
        }""")
        for i in range(30):
            for f in page.frames:
                if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                    enf = f
                    break
            if enf:
                break
            time.sleep(0.5)
    
    if not enf:
        print("  No enforcement. Exiting.", flush=True)
        browser.close()
        exit()
    
    print(f"  Enforcement found: {enf.url[:200]}", flush=True)
    time.sleep(3)
    
    # Now submit login via fetch through PX
    print("[2] Submitting login via fetch (through PX)...", flush=True)
    
    result = page.evaluate("""async () => {
        try {
            const form = document.getElementById('login-form');
            if (!form) return {error: 'no form'};
            
            const fd = new FormData(form);
            const resp = await fetch('/v2/login', {
                method: 'POST',
                body: fd,
                credentials: 'include',
            });
            
            const text = await resp.text();
            return {
                status: resp.status,
                headers: Array.from(resp.headers.entries()).slice(0, 15),
                text: text.substring(0, 500),
            };
        } catch(e) {
            return {error: e.message, stack: e.stack?.substring(0, 200)};
        }
    }""")
    print(f"  Fetch result: {json.dumps(result)[:500]}", flush=True)
    
    # Wait for game-core images
    print("[3] Waiting 15s for match game images...", flush=True)
    gc = None
    images_found = False
    for i in range(30):
        for f in page.frames:
            if 'game-core' in f.url:
                gc = f
                break
        
        if gc:
            try:
                state = gc.evaluate("""() => ({
                    imgs: document.querySelectorAll('img').length,
                    bodyLen: document.body?.innerHTML?.length || 0,
                })""")
                if state['imgs'] > 0 or state['bodyLen'] > 5000:
                    images_found = True
                    print(f"  [+] Challenge at {i*0.5:.0f}s: {json.dumps(state)}", flush=True)
            except:
                pass
        
        if images_found:
            break
        time.sleep(0.5)
    
    print(f"\n  Images found: {images_found}", flush=True)
    
    if gc:
        full_state = gc.evaluate("""() => {
            const body = document.body?.innerHTML || '';
            return {
                bodyLen: body.length,
                bodyPreview: body.substring(0, 1000),
            };
        }""")
        print(f"  GC body: {json.dumps(full_state)[:800]}", flush=True)
    
    # Check enforcement state
    if enf:
        try:
            enf_state = enf.evaluate("""() => {
                const vt = document.getElementById('verification-token');
                return {
                    iframes: document.querySelectorAll('iframe').length,
                    appLen: document.getElementById('app')?.innerHTML?.length || 0,
                    vt: vt?.value?.substring(0, 200) || 'N/A',
                };
            }""")
            print(f"  Enforcement: {json.dumps(enf_state)[:400]}", flush=True)
        except:
            pass
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(5)
    browser.close()
