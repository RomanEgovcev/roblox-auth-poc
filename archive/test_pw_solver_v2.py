import os, time, requests, json
from playwright.sync_api import sync_playwright

NOPECHA_API = "https://api.nopecha.com"
pw_profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=pw_profile, headless=False,
    )
    page = context.pages[0]
    
    for attempt in range(10):
        print(f"\n{'='*40}\nAttempt {attempt+1}")
        page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
        try:
            page.wait_for_selector("#login-username", timeout=15000)
        except:
            print("  Page load issue, retry")
            continue
        page.fill("#login-username", "CheatingHitmanner")
        page.fill("#login-password", "LolKekZek228")
        page.evaluate("""() => {
            document.querySelectorAll('.cookie-banner-wrapper, .cookie-banner-bg, .notification-blue')
                .forEach(e => { if (e) e.style.display = 'none'; });
        }""")
        page.wait_for_timeout(500)
        page.click("#login-button", force=True)
        
        enforcement = None
        game_frame = None
        for i in range(20):
            time.sleep(1)
            for f in page.frames:
                if 'arkoselabs.roblox.com' in f.url and 'enforcement' in f.url:
                    enforcement = f
                if 'ec-game-core' in f.url:
                    game_frame = f
            if enforcement and game_frame:
                print(f"[+] CAPTCHA at {i+1}s - attempt {attempt+1}")
                break
        else:
            print("  No captcha, retry")
            continue
        
        # Found captcha, solve it
        print(f"[*] Game core: {game_frame.url[:120]}")
        
        # Wait for canvas
        for i in range(15):
            if game_frame.evaluate("!!document.querySelector('canvas')"):
                print(f"[+] Canvas ready")
                break
            time.sleep(1)
        
        b64 = game_frame.evaluate("""() => {
            const c = document.querySelector('canvas');
            return c ? c.toDataURL('image/png').split(',')[1] : null;
        }""")
        if not b64:
            print("  No canvas data, retry")
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
        
        # NopeCHA
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
        
        # Click via mouse on canvas
        rect = game_frame.evaluate("""() => {
            const c = document.querySelector('canvas');
            const r = c.getBoundingClientRect();
            return {x: r.left, y: r.top, w: r.width, h: r.height};
        }""")
        tw, th = rect['w'] / 2, rect['h'] / 2
        for i in range(4):
            if click_data[i]:
                page.mouse.click(rect['x'] + (i%2)*tw + tw/2, rect['y'] + (i//2)*th + th/2)
                time.sleep(0.3)
        print("[*] Tiles clicked")
        
        time.sleep(5)
        
        # Check token
        tok = enforcement.evaluate("""() => {
            for (const id of ['FunCaptcha-Token', 'verification-token', 'fc-token']) {
                const el = document.getElementById(id);
                if (el && el.value) return el.value.slice(0, 40);
            }
            return null;
        }""")
        print(f"[*] Token: {tok}")
        
        if tok:
            print("[+] CAPTCHA SOLVED!")
        else:
            print("[-] Token not found - might need more interaction")
        
        input("Enter to continue...")
        break  # Only solve one captcha for now
    
    time.sleep(5)
    context.close()
