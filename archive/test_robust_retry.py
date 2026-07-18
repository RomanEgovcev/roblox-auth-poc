"""Robust retry: prime PX with Enter first, then dispatchEvent click until enforcement appears."""
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
    
    enf_frames = []
    def track_frames(frame):
        if 'arkoselabs.roblox.com' in frame.url and 'enforcement.' in frame.url:
            enf_frames.append(frame)
            print(f"  [+] Enforcement ({len(enf_frames)}): {frame.url[:200]}", flush=True)
    page.on("frameattached", track_frames)
    page.on("framenavigated", track_frames)
    
    print("[1] Loading page...", flush=True)
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(8)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(2)
    
    # Prime PX with Enter events first
    print("[2] Priming PX with dispatchEvent Enter...", flush=True)
    for attempt in range(3):
        page.evaluate("""() => {
            const pw = document.querySelector('input[name="password"]');
            if (!pw) return;
            ['keydown','keypress','keyup'].forEach(evt => {
                pw.dispatchEvent(new KeyboardEvent(evt, {
                    key: 'Enter', code: 'Enter', keyCode: 13, which: 13,
                    bubbles: true, cancelable: true
                }));
            });
        }""")
        time.sleep(2)
    
    # Then dispatchEvent click to trigger enforcement
    print("[3] Dispatching click events to trigger enforcement...", flush=True)
    click_time = time.time()
    
    for attempt in range(10):
        if len(enf_frames) > 0:
            print(f"  Enforcement found at attempt {attempt+1}!", flush=True)
            break
        
        # Dispatch click on button
        page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            if (!btn) return;
            btn.dispatchEvent(new MouseEvent('click', {
                bubbles: true, cancelable: true, view: window
            }));
        }""")
        
        print(f"  Attempt {attempt+1}, waiting 6s...", flush=True)
        for i in range(12):  # 6s
            if len(enf_frames) > 0:
                break
            time.sleep(0.5)
    
    if len(enf_frames) == 0:
        print("  No enforcement after 10 attempts. Exiting.", flush=True)
        browser.close()
        exit()
    
    enf = enf_frames[0]
    print(f"  Enforcement at t={int(time.time()-click_time)}s", flush=True)
    st = re.search(r'&([0-9a-f\-]{36})$', enf.url)
    print(f"  Session: {st.group(1) if st else 'none'}", flush=True)
    
    # Now call React onClick handler
    time.sleep(5)
    
    print("\n[4] Calling React onClick handler...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        if (!btn) return;
        const propsKey = Object.keys(btn).find(k => k.startsWith('__reactProps'));
        if (!propsKey) return;
        const props = btn[propsKey];
        if (props?.onClick) props.onClick({});
    }""")
    
    # Monitor for auth and game-core
    print("  Monitoring 20s...", flush=True)
    auth_found = False
    gc_found = False
    
    for i in range(40):
        # Check frames for game-core
        if not gc_found:
            for f in page.frames:
                if 'game-core' in f.url or 'game_core' in f.url:
                    gc_found = True
                    print(f"  [+] Game-core at {i*0.5:.0f}s!", flush=True)
        
        # Check enforcement
        if not gc_found:
            try:
                iframes = enf.evaluate("document.querySelectorAll('iframe').length")
                if iframes > 0:
                    gc_found = True
                    print(f"  [+] Enforcement has iframes at {i*0.5:.0f}s!", flush=True)
            except:
                pass
        
        if gc_found:
            break
        time.sleep(0.5)
    
    print(f"\n[5] Results...", flush=True)
    print(f"  Game-core: {gc_found}", flush=True)
    print(f"  URL: {page.url[:200]}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(5)
    browser.close()
