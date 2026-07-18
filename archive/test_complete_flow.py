"""Complete flow: dispatchEvent click pre-loads enforcement, then again submits form."""
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
    
    calls = []
    page.on("response", lambda r: calls.append(f"[{r.status}] {r.url[:200]}")
             if 'arkoselabs.roblox.com' in r.url or 'funcaptcha' in r.url or '/v2/login' in r.url or '/v2/user' in r.url else None)
    
    enf_frames = []
    def track_frames(frame):
        if 'arkoselabs.roblox.com' in frame.url and 'enforcement.' in frame.url:
            enf_frames.append(frame)
            print(f"  [+] Enforcement: {frame.url[:200]}", flush=True)
    page.on("frameattached", track_frames)
    page.on("framenavigated", track_frames)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    print("[1] Page loaded", flush=True)
    time.sleep(5)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(2)
    
    # Step 1: Pre-load enforcement with dispatchEvent click
    print("\n[2] dispatchEvent click to pre-load enforcement...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        if (!btn) return;
        btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
    }""")
    time.sleep(2)
    
    # Wait for enforcement
    print("  Waiting for enforcement (10s)...", flush=True)
    for i in range(20):
        if len(enf_frames) > 0:
            print(f"  Enforcement found at {i*0.5:.0f}s!", flush=True)
            break
        time.sleep(0.5)
    
    if len(enf_frames) == 0:
        print("  No enforcement appeared!", flush=True)
        browser.close()
        exit()
    
    enf = enf_frames[0]
    print(f"  URL: {enf.url[:250]}", flush=True)
    st_match = re.search(r'&([0-9a-f\-]{36})$', enf.url)
    if st_match:
        print(f"  Session token: {st_match.group(1)}", flush=True)
    
    # Wait for enforcement to settle
    time.sleep(5)
    
    # Step 2: dispatchEvent click AGAIN to submit form through PX
    print("\n[3] Submitting form (2nd dispatchEvent click)...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        if (!btn) return;
        btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
    }""")
    
    # Step 3: Wait for game-core or auth result
    print("  Waiting for game-core (25s)...", flush=True)
    gc_found = False
    for i in range(50):
        if len(page.frames) > 3:  # More than the initial frames
            for f in page.frames:
                if 'game-core' in f.url or 'game_core' in f.url:
                    gc_found = True
                    print(f"  [+] Game-core: {f.url[:200]}", flush=True)
                    break
        if gc_found:
            break
        
        # Check enforcement state
        try:
            iframes = enf.evaluate("document.querySelectorAll('iframe').length")
            if iframes > 0:
                print(f"  [+] Enforcement has {iframes} iframe(s)!", flush=True)
                gc_found = True
                break
        except:
            pass
        
        # Check for page changes (form submit response)
        if '/login' not in page.url and '/v2/' not in page.url:
            if page.url != 'https://www.roblox.com/login':
                print(f"  Page URL changed: {page.url[:200]}", flush=True)
                break
        
        time.sleep(0.5)
    
    # Final check
    print(f"\n  Final URL: {page.url[:200]}", flush=True)
    print(f"  Game-core: {gc_found}", flush=True)
    
    print(f"\n=== Frames ({len(page.frames)}) ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    print(f"\n=== API calls ({len(calls)}) ===", flush=True)
    for c in calls:
        print(f"  {c}", flush=True)
    
    page.screenshot(path="final_state.png")
    time.sleep(10)
    browser.close()
