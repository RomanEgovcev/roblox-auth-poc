"""Use Playwright Chromium directly (not Chrome 150) with --load-extension."""
import os, time, json, base64, io

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

ext = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_pw"

import shutil
try: shutil.rmtree(profile)
except: pass

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    # Use Playwright's Chromium with extension
    context = p.chromium.launch_persistent_context(
        profile,
        headless=False,
        args=[
            f"--load-extension={ext}",
            "--no-first-run",
            "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"
        ],
        viewport={"width": 1280, "height": 720}
    )
    
    page = context.pages[0] if context.pages else context.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(5)
    
    # Fill
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Track responses
    auth_responses = []
    page.on("response", lambda r: auth_responses.append({"url": r.url[:200], "status": r.status}))
    
    # btn.click() via evaluate
    page.evaluate("document.querySelector('#login-button')?.click()")
    print("[*] Submitted via btn.click()", flush=True)
    
    # Poll for frames
    enf = None; game = None
    for i in range(90):
        for f in page.frames:
            if 'enforcement' in f.url: enf = f
            if 'game-core' in f.url: game = f
        
        auth_resp = [r for r in auth_responses if 'auth.roblox.com' in r['url']]
        auth_status = str(auth_resp[-1]['status']) if auth_resp else 'none'
        
        if i % 10 == 0:
            print(f"[{i}s] auth:{auth_status} frames:{len(page.frames)} game:{bool(game)} enf:{bool(enf)}", flush=True)
        
        if enf and game:
            print(f"[+] Both at {i}s (auth:{auth_status})", flush=True)
            break
        time.sleep(1)
    else:
        print(f"[-] No frames. Auth: {[(r['url'][:60], r['status']) for r in auth_responses]}", flush=True)
        page.screenshot(path="debug_playwright.png")
        context.close()
        exit(1)
    
    # Wait for canvas
    print("[*] Waiting for canvas...", flush=True)
    canvas = None
    for wait_i in range(40):
        for fname, f in [('game-core', game), ('enforcement', enf)]:
            c = f.evaluate("""() => {
                const el = document.querySelector('canvas');
                if (!el) return null;
                try {return el.toDataURL('image/png');} catch(e) {return '__tainted__';}
            }""")
            if c and c != '__tainted__':
                canvas = c; print(f"[{wait_i}s] Canvas from {fname}", flush=True); break
            elif c == '__tainted__':
                print(f"[{wait_i}s] {fname} tainted", flush=True)
        if canvas: break
        time.sleep(1)
    else:
        print("[-] No canvas, full page fallback", flush=True)
        ss = page.screenshot()
        canvas = 'data:image/png;base64,' + base64.b64encode(ss).decode()
    
    task = (enf or game).evaluate("""() => {
        const every = document.querySelectorAll('*');
        for (const e of every) { const t = (e.textContent || '').trim(); if (t.length > 5 && t.length < 300) return t; }
        return 'none';
    }""")
    print(f"Task: {task[:300]}", flush=True)
    
    if canvas:
        img_data = base64.b64decode(canvas.split(',')[1])
        with open("solve_pw.png", "wb") as f: f.write(img_data)
        print(f"[*] Saved solve_pw.png ({len(img_data)} bytes)", flush=True)
    
    # API
    import requests
    proxy = {"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"}
    print("[*] Calling NopeCHA API...", flush=True)
    resp = requests.post("https://api.nopecha.com/v1/recognition",
        json={"type": "funcaptcha_match", "task": task, "image_data": [canvas]},
        proxies=proxy, timeout=60)
    print(f"API: {resp.status_code}", flush=True)
    
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
            print("[+] Clicks done!", flush=True)
            time.sleep(10)
            if 'home' in page.url.lower():
                print("\n[!!!] CAPTCHA SOLVED!", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        print(resp.text[:500], flush=True)

context.close()
