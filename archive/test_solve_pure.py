"""Pure Playwright Chromium, no extension. Submit login, wait for PX frames."""
import os, time, json, base64, io

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

profile = "C:\\Users\\regov\\Desktop\\lua\\pw_pure"
import shutil
try: shutil.rmtree(profile)
except: pass

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        profile, headless=False,
        viewport={"width": 1280, "height": 720}
    )
    page = context.pages[0] if context.pages else context.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(5)
    
    # Fill
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Track
    auth_responses = []
    page.on("response", lambda r: auth_responses.append({"url": r.url[:200], "status": r.status}))
    
    # Submit via btn.click()
    page.evaluate("document.querySelector('#login-button')?.click()")
    print("[*] Submitted", flush=True)
    
    # Wait for enforcement frame
    enf = None; game = None
    for i in range(90):
        for f in page.frames:
            if 'enforcement' in f.url: enf = f
            if 'game-core' in f.url: game = f
        
        auth_resp = [r for r in auth_responses if 'auth.roblox.com' in r['url']]
        auth_status = str(auth_resp[-1]['status']) if auth_resp else 'none'
        
        if i % 10 == 0:
            print(f"[{i}s] auth:{auth_status} frames:{len(page.frames)} game:{bool(game)} enf:{bool(enf)}", flush=True)
            if auth_resp:
                print(f"  Auth: {auth_resp[-1]}", flush=True)
        
        if enf:
            print(f"[+] Enforcement at {i}s (auth:{auth_status})", flush=True)
            break
        time.sleep(1)
    else:
        print(f"[-] No enforcement. Auth: {[(r['url'][:60], r['status']) for r in auth_responses]}", flush=True)
        page.screenshot(path="pure_fail.png")
        context.close()
        exit(1)
    
    print(f"[*] Full frames list: {[f.url[:100] for f in page.frames]}", flush=True)
    
    # Wait for game-core
    for i in range(30):
        for f in page.frames:
            if 'game-core' in f.url: game = f
        if game:
            print(f"[+] Game-core at {i}s", flush=True)
            break
        time.sleep(1)
    
    if not game:
        print("[-] No game-core", flush=True)
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
        print("[-] No canvas", flush=True)
        page.screenshot(path="pure_nocanvas.png")
        # Try full page
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
        with open("solve_pure.png", "wb") as f: f.write(img_data)
        print(f"[*] Saved solve_pure.png ({len(img_data)} bytes)", flush=True)
    
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
