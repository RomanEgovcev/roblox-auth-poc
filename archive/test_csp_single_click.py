"""CSP bypass + single page.click with long wait for auto-submit."""
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
    
    all_responses = []
    page.on("response", lambda r: all_responses.append({
        't': time.time(), 's': r.status, 'u': r.url[:200],
        'h': dict(r.headers)
    }))
    
    enf_frames = []
    def track_frames(frame):
        if 'arkoselabs.roblox.com' in frame.url and 'enforcement.' in frame.url:
            enf_frames.append(frame)
            print(f"  [+] Enforcement ({len(enf_frames)}): {frame.url[:200]}", flush=True)
    page.on("frameattached", track_frames)
    page.on("framenavigated", track_frames)
    
    print("[1] Loading page with CSP bypass...", flush=True)
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    print("\n[2] page.click('#login-button')...", flush=True)
    click_time = time.time()
    page.click("#login-button")
    print(f"  Clicked at t=0s", flush=True)
    
    # Monitor for 60 seconds
    print("  Monitoring (60s)...", flush=True)
    auth_403 = None
    gc_found = False
    
    start = time.time()
    while time.time() - start < 60:
        elapsed = int(time.time() - start)
        
        # Check for auth 403
        for r in all_responses:
            if r['s'] == 403 and '/v2/login' in r['u']:
                if not auth_403:
                    auth_403 = r
                    print(f"  [+] Auth 403 at t={elapsed}s", flush=True)
                    for k, v in r['h'].items():
                        if 'challenge' in k.lower() or 'rblx' in k.lower() or k.startswith('x-'):
                            print(f"    {k}: {v[:300]}", flush=True)
        
        # Check game-core
        if not gc_found:
            for f in page.frames:
                if 'game-core' in f.url or 'game_core' in f.url:
                    gc_found = True
                    print(f"  [+] Game-core at t={elapsed}s: {f.url[:200]}", flush=True)
                    break
        
        if auth_403 and gc_found:
            break
        
        time.sleep(0.5)
    
    total = int(time.time() - start)
    print(f"\n[3] Results (t={total}s)...", flush=True)
    print(f"  Final URL: {page.url[:200]}", flush=True)
    print(f"  Auth 403: {auth_403 is not None}", flush=True)
    print(f"  Game-core: {gc_found}", flush=True)
    print(f"  Enforcement frames: {len(enf_frames)}", flush=True)
    
    # Print last auth/challenge responses
    print(f"\n=== Auth/challenge responses ===", flush=True)
    for r in all_responses:
        if r['s'] in [403, 429] or 'challenge' in r['u']:
            d = r['t'] - click_time
            print(f"  [t={d:.0f}s {r['s']}] {r['u']}", flush=True)
    
    print(f"\n=== All frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    page.screenshot(path="csp_single_click.png")
    time.sleep(10)
    browser.close()
