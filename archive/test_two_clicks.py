"""CSP bypass + two clicks: first pre-loads, second submits."""
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
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    calls = []
    page.on("response", lambda r: calls.append(f"[{r.status}] {r.url[:200]}")
             if 'arkoselabs.roblox.com' in r.url or 'funcaptcha' in r.url or '/v2/login' in r.url else None)
    
    enf_frames = []
    def track_frames(frame):
        if 'arkoselabs.roblox.com' in frame.url and 'enforcement.' in frame.url:
            enf_frames.append(frame)
            print(f"  [+] Enforcement: {frame.url[:200]}", flush=True)
    page.on("frameattached", track_frames)
    page.on("framenavigated", track_frames)
    
    print("[1] Loading page with CSP bypass...", flush=True)
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(8)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(2)
    
    # First click - pre-load enforcement
    print("\n[2] First click (pre-load)...", flush=True)
    page.click("#login-button")
    
    print("  Waiting for enforcement (25s)...", flush=True)
    for i in range(50):
        if len(enf_frames) > 0:
            print(f"  Enforcement found at {i*0.5:.0f}s!", flush=True)
            break
        time.sleep(0.5)
    
    if len(enf_frames) == 0:
        print("  No enforcement!", flush=True)
        browser.close()
        exit()
    
    enf = enf_frames[0]
    print(f"  URL: {enf.url[:250]}", flush=True)
    st_match = re.search(r'&([0-9a-f\-]{36})$', enf.url)
    if st_match:
        print(f"  Session token: {st_match.group(1)}", flush=True)
    
    # Wait for enforcement to fully load
    time.sleep(5)
    
    # Second click - submit form through PX
    print("\n[3] Second click (submit)...", flush=True)
    page.click("#login-button")
    
    # Wait for auth response and game-core
    print("  Waiting for auth + game-core (30s)...", flush=True)
    auth_ok = False
    gc_found = False
    for i in range(60):
        # Check enforcement for game-core iframes
        try:
            iframes = enf.evaluate("document.querySelectorAll('iframe').length")
            if iframes > 0 and not gc_found:
                print(f"  [+] Enforcement has {iframes} iframe(s)!", flush=True)
                # Find the game-core URL
                for f in page.frames:
                    if 'game-core' in f.url or 'game_core' in f.url:
                        print(f"  [+] Game-core: {f.url[:200]}", flush=True)
                        gc_found = True
        except:
            pass
        
        # Check URL change (form submission)
        if '/login' not in page.url and page.url != 'https://www.roblox.com':
            if not auth_ok:
                print(f"  [+] Auth URL changed: {page.url[:200]}", flush=True)
                auth_ok = True
        
        if gc_found:
            break
        time.sleep(0.5)
    
    print(f"\n[4] Results...", flush=True)
    print(f"  Final URL: {page.url[:200]}", flush=True)
    print(f"  Auth succeeded: {auth_ok}", flush=True)
    print(f"  Game-core: {gc_found}", flush=True)
    
    print(f"\n=== Frames ({len(page.frames)}) ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    print(f"\n=== API calls ({len(calls)}) ===", flush=True)
    for c in calls:
        print(f"  {c}", flush=True)
    
    page.screenshot(path="two_clicks.png")
    time.sleep(10)
    browser.close()
