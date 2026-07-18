"""Solve captcha by extending the proven-working detection script."""
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
    
    # Track auth response
    auth_responses = []
    page.on("response", lambda r: auth_responses.append({"url": r.url[:200], "status": r.status}))
    
    page.click("#login-button")
    print("[*] Login submitted", flush=True)
    time.sleep(2)
    
    # Print auth responses so far
    auth_resp = [r for r in auth_responses if 'auth' in r['url'] and 'roblox' in r['url']]
    if auth_resp:
        print(f"Auth: {auth_resp[-1]}", flush=True)
    else:
        print("Auth: none yet", flush=True)
    
    # Wait for game-core (same as working script)
    game = None
    for i in range(60):
        auth_resp = [r for r in auth_responses if 'auth' in r['url'] and 'roblox' in r['url']]
        auth_status = str(auth_resp[-1]['status']) if auth_resp else 'none'
        
        for f in page.frames:
            if 'game-core' in f.url:
                game = f
                print(f"[+] Game-core at {i}s (auth:{auth_status})", flush=True)
                break
        if game:
            break
        if i % 10 == 0:
            print(f"[{i}s] frames:{len(page.frames)} auth:{auth_status} urls:{[f.url[:80] for f in page.frames]}", flush=True)
        time.sleep(1)
    else:
        print("[-] No game-core in 60s", flush=True)
        auth_resp = [r for r in auth_responses if 'auth' in r['url'] and 'roblox' in r['url']]
        print(f"Auth responses: {auth_resp}", flush=True)
        print(f"All responses: {[(r['url'][:80], r['status']) for r in auth_responses]}", flush=True)
        print(f"Frames: {[f.url[:120] for f in page.frames]}", flush=True)
        proc.kill(); exit(1)
    
    time.sleep(3)
    
    # Get task text
    task = game.evaluate("""() => {
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
        print(f"[!] Canvas: {canvas[:50] if canvas else 'None'}", flush=True)
        rect = game.evaluate("""() => {
            const c = document.querySelector('canvas');
            if (!c) return null;
            const r = c.getBoundingClientRect();
            return {x:r.x, y:r.y, w:r.width, h:r.height};
        }""")
        print(f"Rect: {rect}", flush=True)
        if rect and rect['w'] > 10:
            from PIL import Image
            ss = game.screenshot()
            img = Image.open(io.BytesIO(ss))
            r = rect
            cropped = img.crop((r['x'], r['y'], r['x']+r['w'], r['y']+r['h']))
            buf = io.BytesIO(); cropped.save(buf, format='PNG')
            canvas = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
        else:
            ss = game.screenshot()
            canvas = 'data:image/png;base64,' + base64.b64encode(ss).decode()
    
    if not canvas or len(canvas) < 100:
        print(f"[-] Canvas empty", flush=True)
        proc.kill(); exit(1)
    
    img_data = base64.b64decode(canvas.split(',')[1])
    with open("solve_captcha.png", "wb") as f:
        f.write(img_data)
    print(f"[*] Saved solve_captcha.png ({len(img_data)} bytes)", flush=True)
    
    # Call NopeCHA API
    import requests
    proxy = {"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"}
    
    print("[*] Calling NopeCHA API...", flush=True)
    resp = requests.post("https://api.nopecha.com/v1/recognition",
        json={"type": "funcaptcha_match", "task": task, "image_data": [canvas]},
        proxies=proxy, timeout=60)
    
    try:
        result = resp.json()
        print(f"API: {resp.status_code}", flush=True)
        print(json.dumps(result, indent=2, default=str)[:800], flush=True)
        
        if resp.status_code == 200 and result.get('data'):
            coords = result['data']
            print(f"\n[++] SOLUTION: {coords}", flush=True)
            
            for i, (x, y) in enumerate(coords):
                print(f"  Click {i}: ({x}, {y})", flush=True)
                game.click("canvas", position={"x": x, "y": y})
                time.sleep(0.5)
            
            print("[+] All clicks done!", flush=True)
            time.sleep(10)
            
            page_url = page.url
            print(f"URL: {page_url[:200]}", flush=True)
            if 'home' in page_url.lower():
                print("\n[!!!] CAPTCHA SOLVED!", flush=True)
            else:
                body = page.evaluate("() => (document.body?.innerText || '').slice(0, 500)")
                print(f"Body: {body}", flush=True)
        else:
            print(f"[-] No solution: {result}", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        print(resp.text[:500], flush=True)

proc.kill()
