"""Working flow: dispatchEvent -> enforcement -> game-core -> NopeCHA solve."""
import os, time, json, base64, sys, requests

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

# ===== NopeCHA API =====
NOPECHA_KEY = "b4ddcf69a0010e346b7a0358492d9c72ad8b2b16c70e3fd7d2321e0203835ef3"
NOPECHA_PROXY = "http://127.0.0.1:10809"

def solve_captcha(image_data_b64):
    """Send captcha image to NopeCHA API"""
    proxies = {"http": NOPECHA_PROXY, "https": NOPECHA_PROXY}
    resp = requests.post(
        "https://api.nopecha.com/v1",
        json={
            "type": "funcaptcha",
            "image": image_data_b64,
            "key": NOPECHA_KEY
        },
        proxies=proxies,
        timeout=30
    )
    return resp.json()

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Step 1: Trigger PX pre-load with dispatchEvent (NO patch)
    print("[1] Triggering PX pre-load via dispatchEvent...", flush=True)
    page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        if (btn) {
            btn.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
            btn.dispatchEvent(new PointerEvent('pointerup', {bubbles: true}));
            btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
        }
    }""")
    
    # Step 2: Wait for enforcement iframe
    print("[2] Waiting for enforcement iframe (up to 30s)...", flush=True)
    enf_frame = None
    for i in range(60):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                break
        if enf_frame:
            print(f"  [+] Enforcement at {i*0.5:.0f}s!", flush=True)
            break
        time.sleep(0.5)
    
    if not enf_frame:
        print("[-] No enforcement. Trying Enter key...", flush=True)
        page.keyboard.press("Enter")
        time.sleep(10)
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                break
    
    if not enf_frame:
        print("[-] No enforcement after all!", flush=True)
        browser.close()
        sys.exit(1)
    
    enf_url = enf_frame.url
    print(f"  URL: {enf_url[:250]}", flush=True)
    
    # Extract session token
    session_token = ''
    if '#' in enf_url:
        hash_part = enf_url.split('#')[1]
        if '&' in hash_part:
            session_token = hash_part.split('&')[1]
            print(f"  Session: {session_token[:50]}...", flush=True)
    
    # Step 3: Wait for game-core iframe inside enforcement
    print("\n[3] Waiting for game-core in enforcement (up to 120s)...", flush=True)
    game_core_frame = None
    for i in range(240):
        # Check enforcement state
        try:
            enf_state = enf_frame.evaluate("""() => ({
                bodyLen: document.body?.innerHTML?.length || 0,
                iframes: document.querySelectorAll('iframe').length,
                challenge: !!document.getElementById('challenge'),
                funCaptcha: !!document.getElementById('FunCaptcha'),
                appHTML: document.getElementById('app')?.innerHTML?.substring(0, 300) || 'N/A',
            })""")
            
            # Check for game-core frame
            for f in page.frames:
                if 'game-core' in f.url:
                    game_core_frame = f
                    break
                    
        except:
            enf_state = {}
        
        if game_core_frame:
            print(f"  [+] Game-core frame at {i*0.5:.0f}s!", flush=True)
            print(f"    URL: {game_core_frame.url[:200]}", flush=True)
            break
        
        if i == 20:  # After 10s, try clicking to trigger game-core
            try:
                enf_frame.evaluate("""() => {
                    const challenge = document.getElementById('challenge');
                    if (challenge) {
                        challenge.click();
                        console.log('Clicked challenge');
                    }
                    const fc = document.getElementById('FunCaptcha');
                    if (fc) {
                        fc.click();
                        console.log('Clicked FunCaptcha');
                    }
                }""")
                print(f"  [10s] Clicked challenge/FunCaptcha to trigger game-core...", flush=True)
            except Exception as e:
                print(f"  [10s] Click error: {e}", flush=True)
        
        if enf_state.get('iframes', 0) > 0:
            print(f"  [+] Iframes found at {i*0.5:.0f}s! {json.dumps(enf_state)}", flush=True)
        
        if i % 30 == 0 and i > 0:
            print(f"  [{i*0.5:.0f}s] enf: bodyLen={enf_state.get('bodyLen',0)}, iframes={enf_state.get('iframes',0)}", flush=True)
        
        # Check FunCaptcha inner HTML
        if i % 20 == 0:
            try:
                fc_html = enf_frame.evaluate("""() => document.getElementById('FunCaptcha')?.innerHTML?.substring(0, 300) || 'empty'""")
                if fc_html != 'empty':
                    print(f"  [{i*0.5:.0f}s] FunCaptcha inner: {fc_html[:200]}", flush=True)
            except:
                pass
        
        time.sleep(0.5)
    
    if game_core_frame:
        # Step 4: Check game-core for canvas/images
        print(f"\n[4] Checking game-core elements...", flush=True)
        for i in range(30):
            try:
                gc_state = game_core_frame.evaluate("""() => ({
                    canvases: document.querySelectorAll('canvas').length,
                    images: document.querySelectorAll('img').length,
                    buttons: document.querySelectorAll('button').length,
                    bodyLen: document.body?.innerHTML?.length || 0,
                })""")
                print(f"  [{i}s] {json.dumps(gc_state)}", flush=True)
                
                if gc_state['canvases'] > 0 or gc_state['images'] > 3:
                    print(f"  [+] Captcha elements ready!", flush=True)
                    
                    # Take screenshot
                    page.screenshot(path="captcha_ready_full.png")
                    
                    # Get canvas data
                    canvas_data = game_core_frame.evaluate("""() => {
                        const canvas = document.querySelector('canvas');
                        if (!canvas) return null;
                        return canvas.toDataURL('image/png').split(',')[1];
                    }""")
                    
                    if canvas_data:
                        print(f"  Canvas data: {len(canvas_data)} bytes", flush=True)
                        
                        # Send to NopeCHA
                        print(f"\n[5] Sending to NopeCHA...", flush=True)
                        result = solve_captcha(canvas_data)
                        print(f"  NopeCHA result: {json.dumps(result)[:500]}", flush=True)
                    break
            except Exception as e:
                print(f"  [{i}s] Error: {e}", flush=True)
            time.sleep(1)
    
    # ===== SUMMARY =====
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:150]}", flush=True)
    
    print(f"\n=== Enforcement final state ===", flush=True)
    try:
        final = enf_frame.evaluate("""() => ({
            bodyLen: document.body?.innerHTML?.length || 0,
            appHTML: document.getElementById('app')?.innerHTML?.substring(0, 500) || 'N/A',
        })""")
        print(f"  {json.dumps(final)[:400]}", flush=True)
    except:
        pass
    
    time.sleep(10)
    browser.close()
