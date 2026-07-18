"""Full prototype: capture captcha canvas, call NopeCHA API, inject solution."""
import os, time, subprocess, json, sys, base64, requests

chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"
proxy = {"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"}

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
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    page.click("#login-button")
    print("[*] Login submitted", flush=True)
    
    game_frame = None
    for i in range(60):
        for f in page.frames:
            if 'game-core' in f.url:
                game_frame = f
                break
        if game_frame:
            print(f"[+] Game-core at {i}s", flush=True)
            break
        time.sleep(1)
    else:
        print("[-] No game-core in 60s", flush=True)
        proc.kill()
        exit(1)
    
    time.sleep(3)  # Let game render
    
    # 1. Extract task text (try multiple approaches)
    task_text = game_frame.evaluate("""() => {
        const all = document.querySelectorAll('*');
        for (const el of all) {
            const t = (el.textContent || '').trim();
            // Look for instruction text (usually contains "click", "arrow", "rotate", etc.)
            if (t.length > 10 && t.length < 200 &&
                (t.toLowerCase().includes('click') || t.toLowerCase().includes('select') || 
                 t.toLowerCase().includes('choose') || t.toLowerCase().includes('tap') ||
                 t.toLowerCase().includes('image') || t.toLowerCase().includes('picture'))) {
                return t;
            }
        }
        return 'no task found';
    }""")
    print(f"Task: {task_text}", flush=True)
    
    # 2. Extract canvas dataURL
    canvas_data = game_frame.evaluate("""() => {
        const c = document.querySelector('canvas');
        if (!c) return null;
        try {
            return c.toDataURL('image/png');
        } catch(e) {
            return 'tainted:' + e.message;
        }
    }""")
    
    if not canvas_data:
        print("[-] No canvas found", flush=True)
        proc.kill()
        exit(1)
    
    if canvas_data.startswith('tainted:'):
        print(f"[!] Canvas is tainted: {canvas_data[:100]}", flush=True)
        print("[*] Taking screenshot instead...", flush=True)
        # Screenshot game-core and crop to canvas
        canvas_rect = game_frame.evaluate("""() => {
            const c = document.querySelector('canvas');
            if (!c) return null;
            const r = c.getBoundingClientRect();
            return {x: r.x, y: r.y, w: r.width, h: r.height};
        }""")
        print(f"Canvas rect: {canvas_rect}", flush=True)
        
        # Take screenshot of the iframe
        ss_bytes = game_frame.screenshot()
        # For now, we'll save the full iframe screenshot
        with open("game_ss.png", "wb") as img:
            img.write(ss_bytes)
        
        # Use the full screenshot as image data
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(ss_bytes))
        if canvas_rect:
            # Crop to canvas
            x, y, w, h = int(canvas_rect['x']), int(canvas_rect['y']), int(canvas_rect['w']), int(canvas_rect['h'])
            cropped = img.crop((x, y, x+w, y+h))
            buf = io.BytesIO()
            cropped.save(buf, format='PNG')
            canvas_data = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
        
        # If PIL not available, just use the full screenshot
        if not canvas_data or 'tainted' in str(canvas_data):
            canvas_data = 'data:image/png;base64,' + base64.b64encode(ss_bytes).decode()
    else:
        log_msg = f"Canvas dataURL: {len(canvas_data)} chars"
        print(log_msg, flush=True)
    
    print(f"Image data length: {len(canvas_data)} chars", flush=True)
    
    # 3. Call NopeCHA API
    api_payload = {
        "type": "funcaptcha_match",
        "task": task_text,
        "image_data": [canvas_data]
    }
    print(f"\n[*] Calling API...", flush=True)
    
    try:
        resp = requests.post(
            "https://api.nopecha.com/v1/recognition",
            json=api_payload,
            proxies=proxy,
            timeout=30
        )
        print(f"API response: {resp.status_code}", flush=True)
        result = resp.json()
        print(json.dumps(result, indent=2, default=str)[:1000], flush=True)
        
        if resp.status_code == 200 and 'data' in result:
            coords = result['data']
            print(f"\n[+] Solution: {coords}", flush=True)
            
            # 4. Click on solution coordinates
            for i, (x, y) in enumerate(coords):
                print(f"  Click {i}: ({x}, {y})", flush=True)
                game_frame.click("canvas", position={"x": x, "y": y})
                time.sleep(0.3)
            
            print("[+] Clicks done, waiting for captcha to close...", flush=True)
            
            # 5. Wait for captcha to resolve
            for i in range(30):
                frames = page.frames
                has_game = any('game-core' in f.url for f in frames)
                if not has_game:
                    print(f"[+] Captcha CLOSED at {i}s!", flush=True)
                    break
                time.sleep(1)
            else:
                print("[-] Captcha still visible after 30s", flush=True)
        else:
            print(f"[-] API error: {result.get('error', 'unknown')} - {result.get('message', '')}", flush=True)
    except Exception as e:
        print(f"[!] API call failed: {e}", flush=True)

proc.kill()
