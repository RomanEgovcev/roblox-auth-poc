"""Long monitor game-core for challenge images."""
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
    
    # Track all responses
    all_resp = []
    page.on("response", lambda r: all_resp.append({
        't': time.time(), 's': r.status, 'u': r.url[:200]
    }) if '/v2/login' in r.url or '/fc/' in r.url or 'game-core' in r.url or 'arkoselabs' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    
    # Trigger enforcement
    print("[1] Triggering enforcement...", flush=True)
    click_time = time.time()
    for big in range(20):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                break
        if 'enf' in dir() and f and f.url != 'about:blank':
            enf = f
            break
        
        page.evaluate("""() => {
            const pw = document.querySelector('input[name="password"]');
            if (pw) pw.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',keyCode:13,bubbles:true}));
        }""")
        page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            if (btn) btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
        }""")
        time.sleep(5)
    
    # Find enforcement
    enf = None
    for f in page.frames:
        if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
            enf = f
            break
    if not enf:
        print("No enforcement!", flush=True)
        browser.close()
        exit()
    
    print(f"  Enforcement at t={int(time.time()-click_time)}s", flush=True)
    
    # Monitor for game-core AND auth/challenge responses (60s)
    print("[2] Monitoring 60s for game-core + challenge images...", flush=True)
    gc = None
    images_found = False
    auth_found = False
    
    for i in range(120):
        # Find game-core frame
        if not gc:
            for f in page.frames:
                if 'game-core' in f.url or 'game_core' in f.url:
                    gc = f
                    print(f"  [+] Game-core at t={int(time.time()-click_time)}s!", flush=True)
                    print(f"      {gc.url[:200]}", flush=True)
                    break
        
        # Check for auth 403
        if not auth_found:
            for r in all_resp:
                if r['s'] == 403 and '/v2/login' in r['u']:
                    auth_found = True
                    print(f"  [+] Auth 403 at t={int(time.time()-click_time)}s!", flush=True)
        
        # Check game-core for images
        if gc and not images_found:
            try:
                state = gc.evaluate("""() => ({
                    imgs: document.querySelectorAll('img').length,
                    can: document.querySelectorAll('canvas').length,
                    bodyLen: document.body?.innerHTML?.length || 0,
                })""")
                if state['imgs'] > 0 or state['can'] > 0 or state['bodyLen'] > 500:
                    images_found = True
                    print(f"  [+] Challenge data at t={int(time.time()-click_time)}s: {json.dumps(state)}", flush=True)
            except:
                pass
        
        if images_found:
            break
        time.sleep(0.5)
    
    elapsed = int(time.time() - click_time)
    print(f"\n[3] Results at t={elapsed}s", flush=True)
    print(f"  Game-core: {gc is not None}", flush=True)
    print(f"  Auth 403: {auth_found}", flush=True)
    print(f"  Challenge images: {images_found}", flush=True)
    
    if gc:
        state = gc.evaluate("""() => ({
            imgs: document.querySelectorAll('img').length,
            can: document.querySelectorAll('canvas').length,
            bodyLen: document.body?.innerHTML?.length || 0,
            bodyPreview: document.body?.innerHTML?.substring(0, 500) || '',
        })""")
        print(f"  GC state: {json.dumps(state)[:800]}", flush=True)
    
    print(f"\n=== Key responses ===", flush=True)
    for r in all_resp:
        d = r['t'] - click_time
        if d > 0:
            print(f"  [t={d:.0f}s {r['s']}] {r['u']}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    browser.close()
