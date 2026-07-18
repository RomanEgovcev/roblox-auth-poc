"""Login POST to auth.roblox.com to trigger PX challenge."""
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
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[:200]}", flush=True) if 'auth.roblox.com' in r.url or 'arkoselabs' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    print("[1] Login POST to auth.roblox.com...", flush=True)
    result = page.evaluate("""async () => {
        try {
            const fd = new FormData();
            fd.append('username', document.querySelector('input[name="username"]').value);
            fd.append('password', document.querySelector('input[name="password"]').value);
            const ctoken = document.querySelector('input[name="ctoken"]');
            if (ctoken) fd.append('ctoken', ctoken.value);
            
            console.log('Sending login to auth.roblox.com...');
            
            const resp = await fetch('https://auth.roblox.com/v2/login', {
                method: 'POST',
                body: fd,
                credentials: 'include',
            });
            
            const text = await resp.text();
            const headers = {};
            resp.headers.forEach((v, k) => {
                if (k.includes('rblx') || k.includes('challenge') || k === 'content-type') headers[k] = v.substring(0, 100);
            });
            
            return {
                status: resp.status,
                headers: JSON.stringify(headers).substring(0, 400),
                bodyLen: text.length,
                bodyPreview: text.substring(0, 200),
            };
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"  Result: {json.dumps(result)[:500]}", flush=True)
    
    # Wait for enforcement
    print("[2] Waiting 15s for enforcement...", flush=True)
    enf = None
    for i in range(30):
        for f in page.frames:
            if 'arkoselabs' in f.url and 'enforcement.' in f.url:
                enf = f
                break
        if enf:
            print(f"  [+] Enforcement at {i*0.5:.0f}s!", flush=True)
            break
        time.sleep(0.5)
    
    if enf:
        print(f"      {enf.url[:120]}", flush=True)
        time.sleep(3)
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
            state = gc.evaluate("""() => ({
                imgs: document.querySelectorAll('img').length,
                bodyLen: document.body?.innerHTML?.length || 0,
                bodyPreview: document.body?.innerHTML?.substring(0, 400) || '',
            })""")
            print(f"  GC: {json.dumps(state)[:600]}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
