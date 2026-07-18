"""Wait 120s for enforcement after realistic interaction."""
import os, time, json

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
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[:200]}", flush=True) if 'auth.roblox.com/v2/login' in r.url or 'arkoselabs' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Click with dispatchEvent (the method that worked before)
    print("[1] dispatchEvent click + Enter priming...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        for (let i = 0; i < 3; i++)
            btn.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',bubbles:true}));
        btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
    }""")
    
    print("[2] Waiting 120s for enforcement...", flush=True)
    enf, gc = None, None
    t0 = time.time()
    for i in range(240):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url:
                if 'enforcement.' in f.url and not enf:
                    enf = f
                    t = time.time() - t0
                    print(f"  [+] Enforcement at {t:.0f}s!", flush=True)
                if 'game-core' in f.url and not gc:
                    gc = f
                    t = time.time() - t0
                    print(f"  [+] Game-core at {t:.0f}s!", flush=True)
        if enf and gc:
            break
        time.sleep(0.5)
    
    if enf:
        t = time.time() - t0
        print(f"  Enforcement URL: {enf.url[:120]}", flush=True)
    else:
        t = time.time() - t0
        print(f"  No enforcement in {t:.0f}s.", flush=True)
    
    if gc:
        state = gc.evaluate("""() => ({
            imgs: document.querySelectorAll('img').length,
            bodyLen: document.body?.innerHTML?.length || 0,
        })""", timeout=5000)
        print(f"  GC state: {json.dumps(state)}", flush=True)
    
    # Check what auth requests happened
    print(f"\n  Total time: {time.time()-t0:.0f}s", flush=True)
    
    time.sleep(3)
    browser.close()
