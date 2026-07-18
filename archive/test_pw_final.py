import os, time, requests, json
from playwright.sync_api import sync_playwright

NOPECHA_API = "https://api.nopecha.com"
pw_profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')

print("[*] Starting...")
with sync_playwright() as p:
    print("[*] Launching browser...")
    context = p.chromium.launch_persistent_context(
        user_data_dir=pw_profile, headless=False,
        args=[
            "--no-proxy-server",
            "--remote-debugging-port=9222",
        ],
    )
    page = context.pages[0]
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    page.wait_for_selector("#login-username", timeout=60000)
    page.fill("#login-username", "TestAccountOpenCode")
    page.fill("#login-password", "TestAccountOpenCode123")
    page.evaluate("""() => {
        document.querySelectorAll('.cookie-banner-wrapper, .cookie-banner-bg, .notification-blue')
            .forEach(e => { if (e && e.style) e.style.display = 'none'; });
    }""")
    page.wait_for_timeout(500)
    page.click("#login-button", force=True)
    print("[*] Submitted")
    
    # Multi-attempt: if captcha doesn't appear, retry up to 3 times
    for big_try in range(3):
        # Wait for captcha frames
        enforcement = None
        game_frame = None
        for i in range(30):
            time.sleep(1)
            for f in page.frames:
                if 'arkoselabs.roblox.com' in f.url and 'enforcement' in f.url:
                    enforcement = f
                if 'ec-game-core' in f.url:
                    game_frame = f
            if enforcement and game_frame:
                print(f"[+] CAPTCHA at +{i+1}s (big_try {big_try+1})")
                break
        
        if not enforcement or not game_frame:
            print(f"[-] No captcha (big_try {big_try+1})")
            # Check if already logged in
            time.sleep(3)
            print(f"  URL: {page.url[:80]}")
            if 'home' in page.url or 'dashboard' in page.url:
                print("[+] ALREADY LOGGED IN!")
                for c in context.cookies():
                    if c['name'] == '.ROBLOSECURITY':
                        print(f"  Cookie: {c['value'][:60]}...")
                break
            # Navigate and try again
            page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
            page.wait_for_selector("#login-username", timeout=15000)
            page.fill("#login-username", "TestAccountOpenCode")
            page.fill("#login-password", "TestAccountOpenCode123")
            page.evaluate("""() => {
                document.querySelectorAll('.cookie-banner-wrapper, .cookie-banner-bg, .notification-blue')
                    .forEach(e => { if (e && e.style) e.style.display = 'none'; });
            }""")
            page.click("#login-button", force=True)
            continue
        
        # === CAPTCHA FOUND ===
        print(f"[*] Game core: {game_frame.url[:120]}")
        
        # Wait for canvas
        for i in range(15):
            if game_frame.evaluate("!!document.querySelector('canvas')"):
                print(f"[+] Canvas ready at +{i+1}s")
                break
            time.sleep(1)
        else:
            print("[-] No canvas, retry")
            continue
        
        # Get canvas
        b64 = game_frame.evaluate("""() => {
            const c = document.querySelector('canvas');
            return c ? c.toDataURL('image/png').split(',')[1] : null;
        }""")
        if not b64:
            print("[-] Canvas empty")
            continue
        print(f"[*] Canvas: {len(b64)} bytes")
        
        # Get task
        task = game_frame.evaluate("""() => {
            for (const s of document.querySelectorAll('[class*="task"], [class*="instruction"], p, h2, h3, span, strong')) {
                const t = (s.textContent||'').trim();
                if (t.length > 5 && t.length < 200) return t;
            }
            return null;
        }""")
        print(f"[*] Task: {task}")
        
        # NopeCHA
        print("[*] Calling NopeCHA API...")
        try:
            resp = requests.post(f"{NOPECHA_API}/v1/recognition/funcaptcha", json={
                "task": task or "Click on the image of",
                "image_data": [f"data:image/png;base64,{b64}"],
            }, timeout=30)
            result = resp.json()
            print(f"  Response: {json.dumps(result)[:200]}")
        except Exception as e:
            print(f"  API error: {e}")
            continue
        
        if "job_id" not in result:
            print(f"  Unexpected response: {result}")
            continue
        
        # Poll
        click_data = None
        for i in range(30):
            time.sleep(2)
            try:
                r = requests.get(f"{NOPECHA_API}/v1/recognition/funcaptcha?id={result['job_id']}", timeout=15)
                d = r.json()
                print(f"  Poll {i+1}: {json.dumps(d)[:150]}")
                if isinstance(d, list) and len(d) >= 4:
                    click_data = d
                    break
                if isinstance(d, dict) and d.get("error"):
                    print(f"  API error: {d['error']}")
                    break
            except Exception as e:
                print(f"  Poll error: {e}")
                break
        
        if not click_data:
            print("[-] No solution")
            continue
        
        print(f"[+] Solution: {click_data}")
        
        # Click tiles via mouse (most reliable)
        rect = game_frame.evaluate("""() => {
            const c = document.querySelector('canvas');
            const r = c.getBoundingClientRect();
            return {x: r.left, y: r.top, w: r.width, h: r.height};
        }""")
        tw, th = rect['w'] / 2, rect['h'] / 2
        for idx in range(4):
            if click_data[idx]:
                cx = rect['x'] + (idx%2)*tw + tw/2
                cy = rect['y'] + (idx//2)*th + th/2
                page.mouse.click(cx, cy)
                time.sleep(0.5)
        print("[*] Tiles clicked")
        
        time.sleep(5)
        
        # Check token
        tok = enforcement.evaluate("""() => {
            for (const id of ['FunCaptcha-Token', 'verification-token', 'fc-token']) {
                const el = document.getElementById(id);
                if (el && el.value) return id + ': ' + el.value.slice(0, 40);
            }
            return null;
        }""")
        print(f"[*] Token: {tok}")
        
        # Check if login succeeded
        time.sleep(5)
        print(f"[*] URL: {page.url[:80]}")
        if 'home' in page.url or 'dashboard' in page.url:
            print("[+] LOGIN SUCCESS!")
            for c in context.cookies():
                if c['name'] == '.ROBLOSECURITY':
                    print(f"  .ROBLOSECURITY: {c['value'][:60]}...")
        else:
            print("[-] Still on login page")
        
        break  # done with this captcha
    
    input("Enter to close...")
    context.close()
