"""Solve captcha: fresh Chrome + extension, login, wait, extract, API, click."""
import os, subprocess, time, json, base64, io

chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

# Kill old, launch fresh
for _ in range(3):
    os.system(f"taskkill /F /IM chrome.exe 2>NUL")
    time.sleep(1)
proc = subprocess.Popen(
    [chrome, f"--user-data-dir={profile}", f"--load-extension={ext}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(6)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    
    # Submit login
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
        print("[-] No game-core", flush=True)
        proc.kill(); exit(1)
    
    time.sleep(3)
    
    # Get task text
    task = game.evaluate("""() => {
        const all = document.querySelectorAll('*');
        for (const el of all) {
            const t = (el.textContent || '').trim();
            if (t.length > 10 && t.length < 300) return t;
        }
        return 'none';
    }""")
    print(f"Task: {task[:200]}", flush=True)
    
    # Get canvas
    canvas = game.evaluate("""() => {
        const c = document.querySelector('canvas');
        if (!c) return null;
        try { return c.toDataURL('image/png'); }
        catch(e) { return '__tainted__'; }
    }""")
    
    if not canvas or canvas == '__tainted__':
        if canvas == '__tainted__':
            print("[!] Canvas tainted, screenshot+crop", flush=True)
        else:
            print("[!] No canvas found", flush=True)
        # Try different iframes for canvas
        for f in page.frames:
            if 'game-core' in f.url or 'arkoselabs' in f.url:
                c = f.evaluate("""() => {
                    const canvas = document.querySelector('canvas');
                    if (!canvas) return null;
                    try { return canvas.toDataURL('image/png'); }
                    catch(e) { return '__tainted__'; }
                }""")
                if c and c != '__tainted__':
                    canvas = c
                    break
                if c == '__tainted__':
                    # Screenshot crop
                    rect = f.evaluate("""() => {
                        const c = document.querySelector('canvas');
                        if (!c) return null;
                        const r = c.getBoundingClientRect();
                        return {x:r.x, y:r.y, w:r.width, h:r.height};
                    }""")
                    if rect and rect['w'] > 0:
                        from PIL import Image
                        ss = f.screenshot()
                        img = Image.open(io.BytesIO(ss))
                        r = rect
                        if r['w'] > 10 and r['h'] > 10:
                            cropped = img.crop((r['x'], r['y'], r['x']+r['w'], r['y']+r['h']))
                            buf = io.BytesIO(); cropped.save(buf, format='PNG')
                            canvas = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
                            print(f"[+] Canvas from crop: {len(canvas)} chars", flush=True)
                            break
    
    if not canvas or len(canvas) < 100:
        print(f"[-] Failed to get canvas", flush=True)
        print(f"Canvas length: {len(canvas) if canvas else 0}", flush=True)
        proc.kill(); exit(1)
    
    # Save
    img_data = base64.b64decode(canvas.split(',')[1])
    with open("solve_captcha.png", "wb") as f:
        f.write(img_data)
    print(f"[*] Saved solve_captcha.png ({len(img_data)} bytes)", flush=True)
    
    # Call NopeCHA API
    import requests
    proxy = {"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"}
    
    print("[*] Calling NopeCHA API...", flush=True)
    api_start = time.time()
    resp = requests.post("https://api.nopecha.com/v1/recognition",
        json={"type": "funcaptcha_match", "task": task, "image_data": [canvas]},
        proxies=proxy, timeout=60)
    api_time = time.time() - api_start
    print(f"API: {resp.status_code} in {api_time:.1f}s", flush=True)
    
    try:
        result = resp.json()
        print(json.dumps(result, indent=2, default=str)[:800], flush=True)
        
        if resp.status_code == 200 and result.get('data'):
            coords = result['data']
            print(f"\n[++] SOLUTION: {coords}", flush=True)
            
            for i, (x, y) in enumerate(coords):
                print(f"  Click {i}: ({x}, {y})", flush=True)
                game.click("canvas", position={"x": x, "y": y})
                time.sleep(0.5)
            
            print("[+] All clicks done!", flush=True)
            time.sleep(8)
            
            # Check result
            if 'home' in page.url.lower() or 'logout' in page.text_content('body').lower():
                print("\n[!!!] CAPTCHA SOLVED!", flush=True)
            else:
                print(f"URL: {page.url[:200]}", flush=True)
                body = page.text_content('body')
                print(f"Body: {body[:300] if body else 'none'}", flush=True)
        else:
            print(f"[-] API error/empty: {result}", flush=True)
    except Exception as e:
        print(f"Parse error: {e}", flush=True)
        print(resp.text[:500], flush=True)

proc.kill()
