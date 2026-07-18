"""Fix: detect enforcement iframe in main page, find game-core nested."""
import os, time, subprocess, json, sys, base64

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
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    page.click("#login-button")
    print("[*] Submitted", flush=True)
    
    # Wait for enforcement iframe (top-level iframe on main page)
    try:
        page.wait_for_function("""() => {
            for (const f of document.querySelectorAll('iframe')) {
                if (f.src && f.src.includes('arkoselabs')) return true;
            }
            return false;
        }""", timeout=30000)
        print("[+] Enforcement iframe detected!", flush=True)
    except:
        print("[-] No enforcement iframe in 30s", flush=True)
        proc.kill()
        exit(1)
    
    time.sleep(3)  # Wait for game-core to load
    
    # Find game-core frame (nested inside enforcement)
    game_frame = None
    for f in page.frames:
        if 'game-core' in f.url:
            game_frame = f
            print(f"[+] Game-core found: {f.url[:120]}", flush=True)
            break
    
    if not game_frame:
        print("[-] Game-core not found in nested frames", flush=True)
        # List all frames
        for f in page.frames:
            print(f"  {f.url[:120]}", flush=True)
        proc.kill()
        exit(1)
    
    time.sleep(2)
    
    # Extract task
    task = game_frame.evaluate("""() => {
        const all = document.querySelectorAll('*');
        for (const el of all) {
            const t = (el.textContent || '').trim();
            if (t.length > 10 && t.length < 300) return t;
        }
        return JSON.stringify([...document.querySelectorAll('*')].map(e => e.textContent).filter(Boolean).slice(0, 5));
    }""")
    print(f"Task: {task[:200]}", flush=True)
    
    # Canvas
    canvas_data = game_frame.evaluate("""() => {
        const c = document.querySelector('canvas');
        if (!c) return 'no-canvas';
        try { return c.toDataURL('image/png'); }
        catch(e) { return 'tainted'; }
    }""")
    
    if canvas_data == 'tainted' or (canvas_data and canvas_data.startswith('data:') and len(canvas_data) < 1000):
        print("[!] Canvas tainted, using screenshot+crop", flush=True)
        # Get canvas rect
        rect = game_frame.evaluate("""() => {
            const c = document.querySelector('canvas');
            if (!c) return null;
            const r = c.getBoundingClientRect();
            return {x: r.x, y: r.y, w: r.width, h: r.height};
        }""")
        print(f"  Canvas rect: {rect}", flush=True)
        
        ss = game_frame.screenshot()
        print(f"  Screenshot: {len(ss)} bytes", flush=True)
        
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(ss))
        if rect and rect['w'] > 0 and rect['h'] > 0:
            x, y, w, h = int(rect['x']), int(rect['y']), int(rect['w']), int(rect['h'])
            cropped = img.crop((x, y, x+w, y+h))
            buf = io.BytesIO()
            cropped.save(buf, format='PNG')
            canvas_data = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
            print(f"  Cropped: {len(canvas_data)} chars", flush=True)
        else:
            canvas_data = 'data:image/png;base64,' + base64.b64encode(ss).decode()
    elif canvas_data and canvas_data.startswith('data:'):
        print(f"[*] Canvas OK: {len(canvas_data)} chars", flush=True)
    else:
        print(f"[-] Canvas: {canvas_data}", flush=True)
        proc.kill()
        exit(1)
    
    # Call NopeCHA API
    import requests
    proxy = {"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"}
    
    print(f"[*] Calling API...", flush=True)
    resp = requests.post("https://api.nopecha.com/v1/recognition",
        json={"type": "funcaptcha_match", "task": task, "image_data": [canvas_data]},
        proxies=proxy, timeout=30)
    
    print(f"[*] API: {resp.status_code}", flush=True)
    try:
        result = resp.json()
        print(json.dumps(result, indent=2, default=str)[:500], flush=True)
        
        if resp.status_code == 200 and 'data' in result:
            coords = result['data']
            print(f"[+] Solution: {coords}", flush=True)
            
            for i, (x, y) in enumerate(coords):
                print(f"  Click {i}: ({x}, {y})", flush=True)
                game_frame.click("canvas", position={"x": x, "y": y})
                time.sleep(0.3)
            
            print("[+] Clicks done, waiting for redirect...", flush=True)
            time.sleep(5)
            
            # Check if redirect happened
            if 'home' in page.url.lower():
                print("[++] REDIRECTED - CAPTCHA SOLVED!", flush=True)
            else:
                print(f"[*] URL after solve: {page.url[:150]}", flush=True)
                print(f"[*] Frames: {[f.url[:100] for f in page.frames]}", flush=True)
        else:
            print(f"[-] API error", flush=True)
    except Exception as e:
        print(f"Parse error: {e}: {resp.text[:300]}", flush=True)

proc.kill()
