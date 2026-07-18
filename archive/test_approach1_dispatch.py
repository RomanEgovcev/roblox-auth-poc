"""Use dispatchEvent to get valid session token, then use it for enforcement."""
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
    
    arkose_resp = []
    def track_resp(response):
        url = response.url
        if 'arkoselabs.roblox.com' in url or 'game-core' in url:
            arkose_resp.append(f"[{response.status}] {url[:200]}")
    page.on("response", track_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Step 1: dispatchEvent to trigger PX pre-load (gets valid session token)
    print("[1] dispatchEvent on login button (no PX patch)...", flush=True)
    page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        if (btn) btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
    }""")
    
    # Step 2: Wait for enforcement iframe with REAL session token
    print("[2] Waiting for enforcement frame with real session...", flush=True)
    enf_frame = None
    enf_url = None
    for i in range(60):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                enf_url = f.url
                break
        if enf_frame:
            print(f"  [+] Enforcement at {i*0.5:.0f}s: {enf_url[:200]}", flush=True)
            break
        time.sleep(0.5)
    
    if not enf_frame:
        print("  [-] No enforcement frame", flush=True)
        browser.close()
        sys.exit(1)
    
    # Extract session token from enforcement URL
    # URL format: ...enforcement.{hash}.html#{publicKey}&{session_token}
    if '#' in enf_url:
        hash_part = enf_url.split('#')[1]
        if '&' in hash_part:
            session_token = hash_part.split('&')[1]
            print(f"  [+] Session token: {session_token[:40]}...", flush=True)
        else:
            session_token = ''
            print(f"  [-] No session token in URL", flush=True)
    else:
        session_token = ''
        print(f"  [-] No hash in URL", flush=True)
    
    # Step 3: Wait for game-core to load in the enforcement frame
    print(f"\n[3] Waiting for game-core in enforcement (up to 60s)...", flush=True)
    game_ready = False
    for i in range(120):
        try:
            state = enf_frame.evaluate("""() => ({
                challenge: !!document.getElementById('challenge'),
                funCaptcha: !!document.getElementById('FunCaptcha'),
                iframes: document.querySelectorAll('iframe').length,
                appHTML: document.getElementById('app')?.innerHTML?.substring(0, 200) || 'N/A',
                bodyLen: document.body?.innerHTML?.length || 0,
            })""")
            
            if state['challenge'] or state['funCaptcha'] or state['iframes'] > 0:
                print(f"  [+] Game-core at {i*0.5:.0f}s! {json.dumps(state)}", flush=True)
                game_ready = True
                try: enf_frame.screenshot(path="enf_game_ready.png")
                except: pass
                
                # Check for canvas elements (MatchGame)
                canvas_state = enf_frame.evaluate("""() => ({
                    canvases: document.querySelectorAll('canvas').length,
                    buttons: document.querySelectorAll('button').length,
                })""")
                print(f"  [+] Canvas: {canvas_state}", flush=True)
                break
                
        except Exception as e:
            if i % 20 == 0:
                print(f"  [{i*0.5:.0f}s] Error: {e}", flush=True)
        
        if i % 30 == 0 and i > 0:
            print(f"  [{i*0.5:.0f}s] Still waiting...", flush=True)
        time.sleep(0.5)
    
    if not game_ready:
        # Check what's happening in enforcement
        try:
            final = enf_frame.evaluate("""() => ({
                bodyLen: document.body?.innerHTML?.length || 0,
                scripts: document.querySelectorAll('script').length,
                appHTML: document.getElementById('app')?.innerHTML?.substring(0, 500) || 'N/A',
            })""")
            print(f"  [-] No game-core. Enf state: {json.dumps(final)[:400]}", flush=True)
            enf_frame.screenshot(path="enf_no_game.png")
        except Exception as e:
            print(f"  [-] Enf error: {e}", flush=True)
    
    # ===== SUMMARY =====
    print(f"\n=== Arkose API calls ({len(arkose_resp)}) ===", flush=True)
    for r in arkose_resp:
        print(f"  {r}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    page.screenshot(path="approach1_results.png")
    time.sleep(10)
    browser.close()
