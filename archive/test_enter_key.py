"""NO patching. Use real keyboard Enter to trigger PX + login flow."""
import os, time, json, base64, sys

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    network = []
    page.on("response", lambda r: network.append(f"[{r.status}] {r.url[:200]}") 
             if 'arkoselabs.roblox.com' in r.url or 'auth.roblox.com' in r.url or 'game-core' in r.url 
             else None)
    
    # NO PX PATCH - use original PX
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Focus password field and press Enter
    print("[1] Focusing password field...", flush=True)
    page.focus("input[name='password']")
    time.sleep(1)
    
    print("[2] Pressing Enter (real keyboard)...", flush=True)
    page.keyboard.press("Enter")
    
    # Wait for enforcement and auth
    print("[3] Waiting for enforcement + auth (up to 30s)...", flush=True)
    enf_frame = None
    auth_received = False
    for i in range(60):
        # Check auth
        for r in network:
            if 'auth.roblox.com' in r and '/v2/login' in r:
                auth_received = True
        
        # Check enforcement frame
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                break
        
        if enf_frame and auth_received:
            print(f"  [+] Both auth + enforcement at {i*0.5:.0f}s!", flush=True)
            break
        
        if i % 10 == 0 and i > 0:
            print(f"  [{i*0.5:.0f}s] auth={auth_received}, enf={enf_frame is not None}", flush=True)
        time.sleep(0.5)
    
    if not enf_frame:
        print("  [-] No enforcement after 30s", flush=True)
    elif not auth_received:
        print("  [-] No auth after 30s", flush=True)
    else:
        print(f"\n  Enforcement URL: {enf_frame.url[:250]}", flush=True)
        
        # Wait for game-core
        print("\n[4] Waiting for game-core (up to 60s)...", flush=True)
        gc_frame = None
        for i in range(120):
            for f in page.frames:
                if 'game-core' in f.url:
                    gc_frame = f
                    break
            
            if gc_frame:
                print(f"  [+] Game-core at {i*0.5:.0f}s!", flush=True)
                break
            
            if i % 20 == 0 and i > 0:
                enf_state = enf_frame.evaluate("""() => ({
                    bodyLen: document.body?.innerHTML?.length || 0,
                    iframes: document.querySelectorAll('iframe').length,
                })""")
                print(f"  [{i*0.5:.0f}s] enf: {json.dumps(enf_state)}", flush=True)
            time.sleep(0.5)
        
        if gc_frame:
            print(f"    URL: {gc_frame.url[:200]}", flush=True)
            for i in range(15):
                gc = gc_frame.evaluate("""() => ({
                    canvases: document.querySelectorAll('canvas').length,
                    images: document.querySelectorAll('img').length,
                    buttons: document.querySelectorAll('button').length,
                })""")
                print(f"  GC [{i}s]: {json.dumps(gc)}", flush=True)
                if gc['canvases'] > 0 or gc['images'] > 3:
                    print(f"  [+] CAPTCHA READY!", flush=True)
                    page.screenshot(path="captcha_enter.png")
                    break
                time.sleep(1)
    
    print(f"\n=== Network ({len(network)}) ===", flush=True)
    for r in network:
        print(f"  {r}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:180]}", flush=True)
    
    page.screenshot(path="enter_final.png")
    time.sleep(10)
    browser.close()
