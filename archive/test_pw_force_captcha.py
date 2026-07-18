import os, time, requests, json
from playwright.sync_api import sync_playwright

NOPECHA_API = "https://api.nopecha.com"
pw_profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')

print("[*] Starting...")
with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=pw_profile, headless=False,
        args=["--no-proxy-server"],
    )
    page = context.pages[0]
    
    # Rapid failed attempts to trigger captcha
    for attempt in range(12):
        print(f"\n--- Attempt {attempt+1} ---")
        page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
        try:
            page.wait_for_selector("#login-username", timeout=15000)
        except:
            print("  Page load failed, skip")
            continue
        
        page.fill("#login-username", "TestAccountOpenCode")
        page.fill("#login-password", "WrongPass" + str(attempt))
        page.evaluate("""() => {
            document.querySelectorAll('.cookie-banner-wrapper, .cookie-banner-bg, .notification-blue')
                .forEach(e => { if (e && e.style) e.style.display = 'none'; });
        }""")
        page.wait_for_timeout(200)
        page.click("#login-button", force=True)
        
        # Check for captcha frames after each attempt (wait 5s)
        found = False
        for i in range(5):
            time.sleep(1)
            for f in page.frames:
                if 'arkoselabs' in f.url:
                    print(f"  [+ CAPTCHA FRAME at +{i+1}s] {f.url[:100]}")
                    found = True
                    break
            if found:
                break
        
        if found:
            print("[+] Captcha triggered!")
            # Find all frames
            enforcement = None
            game_frame = None
            for i in range(15):
                time.sleep(1)
                for f in page.frames:
                    if 'arkoselabs.roblox.com' in f.url and 'enforcement' in f.url:
                        enforcement = f
                    if 'ec-game-core' in f.url:
                        game_frame = f
                if enforcement and game_frame:
                    break
            
            if not game_frame:
                print("[-] Game frame not found")
                continue
            
            # Wait for canvas
            for i in range(15):
                if game_frame.evaluate("!!document.querySelector('canvas')"):
                    print(f"[+] Canvas ready")
                    break
                time.sleep(1)
            else:
                print("[-] No canvas")
                continue
            
            b64 = game_frame.evaluate("""() => {
                const c = document.querySelector('canvas');
                return c ? c.toDataURL('image/png').split(',')[1] : null;
            }""")
            if not b64:
                print("[-] Canvas empty")
                continue
            print(f"[*] Canvas: {len(b64)} bytes")
            
            task = game_frame.evaluate("""() => {
                for (const s of document.querySelectorAll('[class*="task"], [class*="instruction"], p, h2, h3, span, strong')) {
                    const t = (s.textContent||'').trim();
                    if (t.length > 5 && t.length < 200) return t;
                }
                return null;
            }""")
            print(f"[*] Task: {task}")
            
            # NopeCHA API
            print("[*] Calling NopeCHA...")
            resp = requests.post(f"{NOPECHA_API}/v1/recognition/funcaptcha", json={
                "task": task or "Click on the image of",
                "image_data": [f"data:image/png;base64,{b64}"],
            }, timeout=30)
            result = resp.json()
            print(f"  {json.dumps(result)[:200]}")
            
            if "job_id" not in result:
                print(f"  API error: {result}")
                continue
            
            click_data = None
            for i in range(30):
                time.sleep(2)
                r = requests.get(f"{NOPECHA_API}/v1/recognition/funcaptcha?id={result['job_id']}", timeout=15)
                d = r.json()
                print(f"  Poll {i+1}: {json.dumps(d)[:150]}")
                if isinstance(d, list) and len(d) >= 4:
                    click_data = d
                    print(f"[+] Solution: {d}")
                    break
                if isinstance(d, dict) and d.get("error"):
                    print(f"  Error: {d['error']}")
                    break
            
            if not click_data:
                continue
            
            # Click tiles
            rect = game_frame.evaluate("""() => {
                const c = document.querySelector('canvas');
                const r = c.getBoundingClientRect();
                return {x: r.left, y: r.top, w: r.width, h: r.height};
            }""")
            tw, th = rect['w'] / 2, rect['h'] / 2
            for idx in range(4):
                if click_data[idx]:
                    page.mouse.click(rect['x'] + (idx%2)*tw + tw/2, rect['y'] + (idx//2)*th + th/2)
                    time.sleep(0.3)
            print("[*] Tiles clicked via mouse")
            
            time.sleep(5)
            
            tok = enforcement.evaluate("""() => {
                for (const id of ['FunCaptcha-Token', 'verification-token', 'fc-token']) {
                    const el = document.getElementById(id);
                    if (el && el.value) return id + ': ' + el.value.slice(0, 40);
                }
                return null;
            }""")
            print(f"[*] Token: {tok}")
            
            # Try clicking submit again
            page.click("#login-button", force=True)
            time.sleep(5)
            print(f"[*] URL after resubmit: {page.url[:80]}")
            
            if 'home' in page.url:
                print("[+] LOGIN SUCCESS!")
                for c in context.cookies():
                    if c['name'] == '.ROBLOSECURITY':
                        print(f"  .ROBLOSECURITY: {c['value'][:60]}...")
            
            break  # Done
        
        # Brief pause between attempts
        time.sleep(1)
    
    else:
        print("\n[-] No captcha after 12 attempts")
    
    input("Enter to close...")
    context.close()
