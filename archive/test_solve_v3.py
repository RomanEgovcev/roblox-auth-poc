"""Solve captcha: based on working test_captcha_state.py approach."""
import os, time, subprocess, json, base64, io

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
    print("[*] Login submitted", flush=True)
    
    # Wait for game-core
    game = None
    for i in range(90):
        for f in page.frames:
            if 'game-core' in f.url:
                game = f
                print(f"[+] Game-core at {i}s", flush=True)
                break
        if game:
            break
        time.sleep(1)
    else:
        print("[-] No game-core in 90s", flush=True)
        # Dump frames
        print(f"Frames: {[f.url[:120] for f in page.frames]}", flush=True)
        proc.kill(); exit(1)
    
    time.sleep(3)
    
    # Get task text from game-core frame
    task = game.evaluate("""() => {
        const el = document.querySelector('[class*=prompt], [class*=task], [class*=challenge]');
        if (el) return el.textContent.trim();
        const all = document.querySelectorAll('h1, h2, h3, p, [class*=text], [class*=heading]');
        for (const e of all) {
            const t = (e.textContent || '').trim();
            if (t.length > 5 && t.length < 300) return t;
        }
        const every = document.querySelectorAll('*');
        for (const e of every) {
            const t = (e.textContent || '').trim();
            if (t.length > 5 && t.length < 300) return t;
        }
        return 'none';
    }""")
    print(f"Task: {task[:300]}", flush=True)
    
    # Get canvas
    canvas = game.evaluate("""() => {
        const c = document.querySelector('canvas');
        if (!c) return null;
        try { return c.toDataURL('image/png'); }
        catch(e) { return '__tainted__'; }
    }""")
    
    if not canvas or canvas == '__tainted__':
        print(f"[!] Canvas: {canvas}", flush=True)
        # Screenshot crop from game-core
        rect = game.evaluate("""() => {
            const c = document.querySelector('canvas');
            if (!c) return null;
            const r = c.getBoundingClientRect();
            return {x:r.x, y:r.y, w:r.width, h:r.height};
        }""")
        print(f"Canvas rect: {rect}", flush=True)
        if rect and rect['w'] > 10 and rect['h'] > 10:
            from PIL import Image
            ss = game.screenshot()
            img = Image.open(io.BytesIO(ss))
            r = rect
            cropped = img.crop((r['x'], r['y'], r['x']+r['w'], r['y']+r['h']))
            buf = io.BytesIO(); cropped.save(buf, format='PNG')
            canvas = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
        else:
            # full game frame screenshot
            ss = game.screenshot()
            canvas = 'data:image/png;base64,' + base64.b64encode(ss).decode()
    
    if not canvas or len(canvas) < 100:
        print(f"[-] Canvas empty ({len(canvas) if canvas else 0})", flush=True)
        proc.kill(); exit(1)
    
    img_data = base64.b64decode(canvas.split(',')[1])
    with open("solve_captcha.png", "wb") as f:
        f.write(img_data)
    print(f"[*] Saved solve_captcha.png ({len(img_data)} bytes)", flush=True)
    
    # Call NopeCHA API through VPN proxy
    import requests
    proxy = {"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"}
    
    print("[*] Calling NopeCHA API...", flush=True)
    api_start = time.time()
    
    # Try different API formats
    payloads = [
        {"type": "funcaptcha_match", "task": task, "image_data": [canvas]},
        {"type": "funcaptcha", "task": task, "image_data": [canvas]},
        {"type": "funcaptcha_match", "image_data": {"task": task, "image": [canvas]}},
    ]
    
    result = None
    for pi, payload in enumerate(payloads):
        print(f"  Try payload {pi}: type={payload.get('type')}", flush=True)
        try:
            resp = requests.post("https://api.nopecha.com/v1/recognition",
                json=payload, proxies=proxy, timeout=30)
            print(f"  -> {resp.status_code}", flush=True)
            if resp.status_code == 200:
                result = resp.json()
                print(f"  Body: {json.dumps(result, default=str)[:500]}", flush=True)
                if result.get('data'):
                    break
            else:
                print(f"  -> {resp.text[:200]}", flush=True)
        except Exception as e:
            print(f"  -> Error: {e}", flush=True)
    
    api_time = time.time() - api_start
    print(f"API total: {api_time:.1f}s", flush=True)
    
    if result and isinstance(result, dict) and result.get('data'):
        coords = result['data']
        print(f"\n[++] SOLUTION: {coords}", flush=True)
        
        # Try both game-core and enforcement frame for clicking
        enf = None
        for f in page.frames:
            if 'enforcement' in f.url:
                enf = f
                break
        
        target = game if game else enf
        for i, (x, y) in enumerate(coords):
            print(f"  Click {i}: ({x}, {y}) on {target.url[:60]}", flush=True)
            target.click("canvas", position={"x": x, "y": y})
            time.sleep(0.5)
        
        print("[+] All clicks done!", flush=True)
        time.sleep(10)
        
        # Check result
        page_url = page.url
        print(f"URL: {page_url[:200]}", flush=True)
        if 'home' in page_url.lower():
            print("\n[!!!] CAPTCHA SOLVED!", flush=True)
        else:
            body = page.evaluate("() => (document.body?.innerText || '').slice(0, 500)")
            print(f"Body: {body}", flush=True)
    else:
        print(f"[-] No solution from API", flush=True)
        if result:
            print(f"Result: {json.dumps(result, default=str)[:500]}", flush=True)

proc.kill()
