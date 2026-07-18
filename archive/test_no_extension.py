"""Test: captcha without extension - does the game start normally?"""
import os, time, json, base64, io

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(3)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False,
        args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    auth_responses = []
    page.on("response", lambda r: auth_responses.append({"url": r.url[:200], "status": r.status}))
    
    page.click("#login-button")
    print("[*] Login submitted", flush=True)
    
    # Poll for enforcement and game-core
    game = None
    enf = None
    for i in range(90):
        auth_resp = [r for r in auth_responses if 'auth.roblox.com' in r['url']]
        auth_status = str(auth_resp[-1]['status']) if auth_resp else 'none'
        
        for f in page.frames:
            if 'game-core' in f.url:
                game = f
            if 'enforcement' in f.url and 'roblox.com' in f.url:
                enf = f
        
        if i % 10 == 0 or (game and enf):
            print(f"[{i}s] auth:{auth_status} frames:{len(page.frames)} game:{bool(game)} enf:{bool(enf)}", flush=True)
            if i % 30 == 0:
                print(f"  Frames: {[f.url[:100] for f in page.frames]}", flush=True)
        
        if game and enf:
            # Check for canvas every second
            cinfo = game.evaluate("""() => {
                const c = document.querySelector('canvas');
                if (!c) return {canvas: false};
                const r = c.getBoundingClientRect();
                return {canvas: true, w: r.width, h: r.height, x: r.x, y: r.y};
            }""")
            if cinfo and cinfo.get('canvas'):
                print(f"[>>] Canvas FOUND at {i}s: {cinfo}", flush=True)
                break
        
        time.sleep(1)
    else:
        print("[-] Canvas not found in 90s", flush=True)
    
    # Print final state
    print(f"\nURL: {page.url[:200]}", flush=True)
    print(f"Frames: {[f.url[:120] for f in page.frames]}", flush=True)
    
    if game:
        html = game.evaluate("() => document.body?.innerHTML?.slice(0, 2000) || 'none'")
        print(f"Game body HTML: {html[:500]}", flush=True)
        cinfo = game.evaluate("""() => {
            const c = document.querySelector('canvas');
            if (!c) return 'no canvas';
            return {w: c.width, h: c.height, tag: c.tagName};
        }""")
        print(f"Canvas: {cinfo}", flush=True)
    
    if enf:
        html = enf.evaluate("() => document.body?.innerHTML?.slice(0, 2000) || 'none'")
        print(f"Enforcement HTML: {html[:500]}", flush=True)
    
    print(f"\nAuth responses: {auth_resp}", flush=True)
    
    time.sleep(5)
    browser.close()
