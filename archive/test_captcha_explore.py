"""Proper: one login, wait for captcha, explore & call API."""
import os, time, subprocess, json, sys

chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

proc = subprocess.Popen(
    [chrome, f"--user-data-dir={profile}", f"--load-extension={ext}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(6)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    
    # Find the main page
    page = None
    for pg in ctx.pages:
        if 'roblox' in pg.url or pg.url == 'about:blank':
            page = pg
            break
    if not page:
        page = ctx.new_page()
    
    captcha_detected = False
    
    def on_frame(f):
        global captcha_detected
        url = f.url
        if 'arkoselabs' in url:
            print(f"[F] {url[:150]}", flush=True)
            if 'enforcement' in url:
                captcha_detected = True
    
    page.on("framenavigated", on_frame)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    
    # Fill and submit
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Monitor all responses for 403
    responses = []
    page.on("response", lambda r: responses.append({"url": r.url, "status": r.status}))
    
    page.click("#login-button")
    print("[*] Login submitted, waiting for captcha...", flush=True)
    
    # Wait for captcha
    for i in range(30):
        if captcha_detected:
            print(f"[+] Captcha detected at {i}s", flush=True)
            break
        time.sleep(1)
    else:
        print("[-] No captcha in 30s", flush=True)
        # Check what happened - maybe the page redirected
        print(f"Current URL: {page.url[:200]}", flush=True)
        print(f"Pages: {[p.url[:100] for p in ctx.pages]}", flush=True)
        # Check for login response
        auth_resp = [r for r in responses if 'auth.roblox.com' in r['url']]
        if auth_resp:
            print(f"Auth response: {auth_resp[-1]}")
        proc.kill()
        sys.exit(1)
    
    # Captcha appeared! Explore frames
    print(f"\n=== Exploring captcha ===")
    all_frames = page.frames
    print(f"Total frames: {len(all_frames)}")
    
    enf_frame = None
    game_frame = None
    for f in all_frames:
        url = f.url[:200]
        if 'enforcement' in url:
            enf_frame = f
            print(f"  Enforcement: {url}")
        if 'game-core' in url:
            game_frame = f
            print(f"  Game-core: {url}")
        if 'arkoselabs' in url and 'enforcement' not in url and 'game-core' not in url:
            print(f"  Other: {url}")
    
    # Explore enforcement iframe HTML
    if enf_frame:
        try:
            html = enf_frame.evaluate("() => document.body?.innerHTML?.slice(0, 5000) || 'no body'")
            print(f"\n=== Enforcement iframe HTML ===")
            print(html[:3000])
        except Exception as e:
            print(f"  [E] {e}")
    
    # Explore game core frame
    if game_frame:
        try:
            # Find canvas
            canvas = game_frame.evaluate("""() => {
                const c = document.querySelector('canvas');
                if (!c) return {msg: 'no canvas'};
                return {
                    w: c.width,
                    h: c.height,
                    type: c.getContext ? '2d' : 'webgl/unknown'
                };
            }""")
            print(f"\n=== Game canvas ===")
            print(json.dumps(canvas, indent=2))
            
            if canvas.get('w', 0) > 0:
                # Screenshot the game iframe
                ss = game_frame.screenshot()
                with open("game_captcha.png", "wb") as img:
                    img.write(ss)
                print(f"Game screenshot: {len(ss)} bytes -> game_captcha.png")
        except Exception as e:
            print(f"  [E] canvas: {e}")
    
    # Take full page screenshot
    ss = page.screenshot()
    with open("full_captcha.png", "wb") as img:
        img.write(ss)
    print(f"\nFull screenshot: {len(ss)} bytes -> full_captcha.png")
    
    print("\nDone. Check screenshots for captcha structure.")

proc.kill()
