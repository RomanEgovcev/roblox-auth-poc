"""Bypass proxy for Roblox (avoid 429), use proxy only for NopeCHA API."""
import os, time, subprocess, json, sys, base64

chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

# Bypass proxy for Roblox domains -> Russian IP (not rate-limited)
# Only proxy for NopeCHA API
proc = subprocess.Popen(
    [chrome, f"--user-data-dir={profile}", f"--load-extension={ext}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*", "--no-proxy-server",
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
    
    # Check auth response
    auth_status = [0]
    page.on("response", lambda r: (auth_status.__setitem__(0, r.status) if 'auth.roblox.com' in r.url else None))
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    page.click("#login-button")
    print("[*] Submitted", flush=True)
    
    # Wait for enforcement
    enf = None
    for i in range(30):
        if auth_status[0]:
            print(f"[{i}s] auth:{auth_status[0]}", flush=True)
        for f in page.frames:
            if 'arkoselabs' in f.url:
                enf = f
                break
        if enf:
            print(f"[+] Enforcement at {i}s", flush=True)
            break
        time.sleep(1)
    else:
        print(f"[-] No captcha in 30s. auth:{auth_status[0]}", flush=True)
        print(f"URL: {page.url[:200]}", flush=True)
        print(f"Frames: {[f.url[:100] for f in page.frames]}", flush=True)
        proc.kill()
        exit(1)
    
    # Wait for game-core
    game = None
    for i in range(30):
        for f in page.frames:
            if 'game-core' in f.url:
                game = f
                break
        if game:
            print(f"[+] Game-core at {i}s", flush=True)
            break
        time.sleep(1)
    else:
        print("[-] No game-core", flush=True)
        proc.kill()
        exit(1)
    
    time.sleep(2)
    
    # Get task
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
    
    if canvas == '__tainted__':
        print("[!] Tainted, screenshot+crop", flush=True)
        rect = game.evaluate("""() => {
            const c = document.querySelector('canvas'); if (!c) return null;
            const r = c.getBoundingClientRect(); return {x:r.x, y:r.y, w:r.width, h:r.height};
        }""")
        ss = game.screenshot()
        if rect and rect['w'] > 0:
            from PIL import Image; import io
            img = Image.open(io.BytesIO(ss))
            c = rect
            cropped = img.crop((c['x'], c['y'], c['x']+c['w'], c['y']+c['h']))
            buf = io.BytesIO(); cropped.save(buf, format='PNG')
            canvas = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
        else:
            canvas = 'data:image/png;base64,' + base64.b64encode(ss).decode()
    
    print(f"Canvas: {len(canvas)} chars", flush=True)
    
    # Save canvas for debugging
    img_data = base64.b64decode(canvas.split(',')[1])
    with open("real_captcha.png", "wb") as f:
        f.write(img_data)
    print(f"Saved real_captcha.png ({len(img_data)} bytes)", flush=True)
    
    # Call NopeCHA API THROUGH PROXY
    import requests
    proxy = {"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"}
    
    print("[*] Calling NopeCHA API...", flush=True)
    resp = requests.post("https://api.nopecha.com/v1/recognition",
        json={"type": "funcaptcha_match", "task": task, "image_data": [canvas]},
        proxies=proxy, timeout=30)
    
    print(f"API: {resp.status_code}", flush=True)
    try:
        result = resp.json()
        print(json.dumps(result, indent=2, default=str)[:500], flush=True)
        
        if resp.status_code == 200 and 'data' in result:
            coords = result['data']
            print(f"\n[++] SOLUTION: {coords}", flush=True)
            
            for i, (x, y) in enumerate(coords):
                print(f"  Click {i}: ({x}, {y})", flush=True)
                game.click("canvas", position={"x": x, "y": y})
                time.sleep(0.3)
            
            print("[+] Clicks done!", flush=True)
            time.sleep(5)
            
            if 'home' in page.url.lower():
                print("\n[!!!] CAPTCHA SOLVED - REDIRECTED HOME!", flush=True)
            else:
                print(f"[*] URL: {page.url[:150]}", flush=True)
        else:
            print(f"[-] API returned error: {result}", flush=True)
    except Exception as e:
        print(f"Parse error: {e}", flush=True)
        print(resp.text[:500], flush=True)

proc.kill()
