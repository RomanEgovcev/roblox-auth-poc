"""dispatchEvent click once, wait 30s for auto-submit behavior."""
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
    
    all_requests = []
    page.on("response", lambda r: all_requests.append({
        't': time.time(), 's': r.status, 'u': r.url[:200],
    }) if '/v2/login' in r.url or '/v2/user' in r.url or 'auth' in r.url else None)
    
    enf_frames = []
    def track_frames(frame):
        if 'arkoselabs.roblox.com' in frame.url and 'enforcement.' in frame.url:
            enf_frames.append(frame)
            print(f"  [+] Enforcement: {frame.url[:200]}", flush=True)
    page.on("frameattached", track_frames)
    page.on("framenavigated", track_frames)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    print("[1] Single dispatchEvent click...", flush=True)
    click_time = time.time()
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        if (btn) btn.dispatchEvent(
            new MouseEvent('click', {bubbles: true, cancelable: true, view: window})
        );
    }""")
    
    print("  Monitoring 30s...", flush=True)
    auth_found = False
    gc_found = False
    nav_found = False
    
    start = time.time()
    while time.time() - start < 30:
        elapsed = int(time.time() - start)
        
        # Check for auth responses
        for r in all_requests:
            if r['s'] == 403 and '/v2/login' in r['u'] and not auth_found:
                auth_found = True
                print(f"  [+] Auth 403 at t={elapsed}s!", flush=True)
        
        # Check for game-core
        if not gc_found:
            for f in page.frames:
                if 'game-core' in f.url or 'game_core' in f.url:
                    gc_found = True
                    print(f"  [+] Game-core at t={elapsed}s!", flush=True)
        
        # Check for navigation
        if not nav_found and page.url != 'https://www.roblox.com/login' and '/login' not in page.url:
            nav_found = True
            print(f"  [+] Navigated to: {page.url[:200]} at t={elapsed}s!", flush=True)
        
        # Check enforcement for iframes
        if not gc_found and len(enf_frames) > 0:
            try:
                iframes = enf_frames[0].evaluate("document.querySelectorAll('iframe').length")
                if iframes > 0:
                    gc_found = True
                    print(f"  [+] Enforcement has {iframes} iframe(s) at t={elapsed}s!", flush=True)
            except:
                pass
        
        if auth_found or gc_found or nav_found:
            if gc_found and auth_found:
                break
        
        time.sleep(0.5)
    
    print(f"\n[2] Results (t={int(time.time()-start)}s)...", flush=True)
    print(f"  URL: {page.url[:200]}", flush=True)
    print(f"  Auth 403: {auth_found}", flush=True)
    print(f"  Game-core: {gc_found}", flush=True)
    print(f"  Navigated: {nav_found}", flush=True)
    print(f"  Enforcement frames: {len(enf_frames)}", flush=True)
    
    print(f"\n=== All frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    print(f"\n=== Auth/Login requests ===", flush=True)
    for r in all_requests:
        d = r['t'] - click_time
        print(f"  [t={d:.0f}s {r['s']}] {r['u']}", flush=True)
    
    page.screenshot(path="single_click_30s.png")
    time.sleep(5)
    browser.close()
