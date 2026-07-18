"""Full flow: trigger PX, get enforcement, submit form, get images."""
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
    
    page.on("response", lambda r: None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Trigger PX
    print("[1] Triggering PX (dispatchEvent click)...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        for (let i = 0; i < 3; i++)
            btn.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',bubbles:true}));
        btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
    }""")
    
    # Wait for enforcement + game-core
    print("[2] Waiting for enforcement + game-core...", flush=True)
    enf, gc = None, None
    for i in range(40):
        for f in page.frames:
            if 'enforcement.' in f.url:
                if not enf:
                    print(f"  [+] Enforcement at {i*0.5:.0f}s!", flush=True)
                    enf = f
            if 'game-core' in f.url:
                if not gc:
                    print(f"  [+] Game-core at {i*0.5:.0f}s!", flush=True)
                    gc = f
        if enf and gc:
            break
        time.sleep(0.5)
    
    if not gc:
        print("  Game-core not found!", flush=True)
        browser.close()
        exit()
    
    print(f"  Enforcement: {enf.url[:120]}", flush=True)
    print(f"  Game-core: {gc.url[:120]}", flush=True)
    
    # Wait for game-core to stabilize
    time.sleep(5)
    
    # Check initial game-core state
    gc_state = gc.evaluate("""() => ({
        imgs: document.querySelectorAll('img').length,
        bodyLen: document.body?.innerHTML?.length || 0,
        bodyPreview: document.body?.innerHTML?.substring(0, 500) || '',
    })""")
    print(f"\n[3] GC initial: {json.dumps(gc_state)[:600]}", flush=True)
    
    # Check if login button still exists
    btn_state = page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        return {
            exists: !!btn,
            rect: btn ? btn.getBoundingClientRect() : null,
            hasOnClick: btn ? (Object.keys(btn).find(k => k.startsWith('__reactProps')) ? true : false) : false,
        };
    }""")
    print(f"  Button: {json.dumps(btn_state)[:300]}", flush=True)
    
    # Submit via React onClick or fetch
    if btn_state.get('exists'):
        print("\n[4] Submitting via React onClick...", flush=True)
        page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            const pk = Object.keys(btn).find(k => k.startsWith('__reactProps'));
            btn[pk].onClick({});
        }""")
    else:
        print("\n[4] Submitting via fetch...", flush=True)
        page.evaluate("""async () => {
            const fd = new FormData();
            fd.append('username', document.querySelector('input[name="username"]').value);
            fd.append('password', document.querySelector('input[name="password"]').value);
            const resp = await fetch('https://auth.roblox.com/v2/login', {
                method: 'POST', body: fd, credentials: 'include'
            });
            return resp.status;
        }""")
    
    # Wait for challenge images
    print("[5] Waiting 20s for challenge images...", flush=True)
    for i in range(40):
        state = gc.evaluate("""() => ({
            imgs: document.querySelectorAll('img').length,
            bodyLen: document.body?.innerHTML?.length || 0,
        })""")
        if state['imgs'] > 0:
            print(f"  [+] {state['imgs']} images at {i*0.5:.0f}s!", flush=True)
            # Extract image URLs
            urls = gc.evaluate("""() => 
                Array.from(document.querySelectorAll('img')).map(i => i.src).filter(s => s)
            """)
            print(f"  Image URLs: {json.dumps(urls)[:600]}", flush=True)
            break
        if i % 10 == 0:
            print(f"  t={i*0.5:.0f}s: {json.dumps(state)}", flush=True)
        time.sleep(0.5)
    
    # Final game-core state
    final = gc.evaluate("""() => {
        const body = document.body?.innerHTML || '';
        return {
            imgs: document.querySelectorAll('img').length,
            bodyLen: body.length,
            bodyPreview: body.substring(0, 1500),
        };
    }""")
    print(f"\n  Final GC: {json.dumps(final)[:800]}", flush=True)
    
    # Check verification token
    if enf:
        try:
            vt = enf.evaluate("""() => {
                const vt = document.getElementById('verification-token');
                return vt && vt.value ? vt.value.substring(0, 200) : 'N/A';
            }""", timeout=5000)
            print(f"  VT: {vt}", flush=True)
        except:
            print(f"  VT: error", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
