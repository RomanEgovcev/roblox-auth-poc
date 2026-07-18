"""Full solve using React onClick handler directly."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    # Track BEFORE anything
    auth_responses = []
    page.on("response", lambda r: auth_responses.append({"url": r.url[:200], "status": r.status}) if 'auth.roblox' in r.url else None)
    page.on("request", lambda r: auth_responses.append({"url": r.url[:200], "method": r.method}) if 'auth.roblox' in r.url and r.url.endswith('/login') else None)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Submitting via React onClick handler...", flush=True)
    page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        const reactKey = Object.keys(btn).find(k => k.startsWith('__reactProps'));
        const props = btn[reactKey];
        if (typeof props.onClick === 'function') {
            props.onClick({type: 'click', target: btn, currentTarget: btn, bubbles: true, cancelable: true});
            return {success: true};
        }
        return {error: 'no onClick'};
    }""")
    print("[*] Submitted", flush=True)
    
    # Wait for auth response
    t0 = time.time()
    auth_done = False
    while time.time() - t0 < 15:
        if any(('auth.roblox' in r['url'] and not r['url'].endswith('/login')) for r in auth_responses):
            auth_done = True
            break
        time.sleep(0.5)
    
    print(f"Auth responses: {[(r['url'][:60], r.get('status','?')) for r in auth_responses]}", flush=True)
    
    # Wait for enforcement
    print("[*] Waiting for PX frames...", flush=True)
    enf = None; game = None
    for i in range(90):
        for f in page.frames:
            if 'enforcement' in f.url: enf = f
            if 'game-core' in f.url: game = f
        if i % 10 == 0:
            auth_status = [r for r in auth_responses if 'auth.roblox' in r['url'] and 'status' in r]
            print(f"[{i}s] auth:{str(auth_status[-1]['status']) if auth_status else 'none'} frames:{len(page.frames)} enf:{bool(enf)} game:{bool(game)}", flush=True)
        if enf: break
        time.sleep(1)
    else:
        print(f"[-] No enforcement", flush=True)
        page.screenshot(path="noenf.png")
        input("Enter...")
        browser.close()
        exit(1)
    
    print(f"[+] Frames: {[f.url[:100] for f in page.frames]}", flush=True)
    
    # Wait for game-core
    for i in range(30):
        for f in page.frames:
            if 'game-core' in f.url: game = f
        if game: break
        time.sleep(1)
    
    if not game:
        print("[-] No game-core, using enforcement for canvas", flush=True)
        game = enf
    
    # Get canvas
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
        page.screenshot(path="nocanvas.png")
        input("Enter...")
        browser.close()
        exit(1)
    
    # Get task
    task = (enf or game).evaluate("""() => {
        const every = document.querySelectorAll('*');
        for (const e of every) { const t = (e.textContent || '').trim(); if (t.length > 5 && t.length < 300) return t; }
        return 'none';
    }""")
    print(f"Task: {task[:300]}", flush=True)
    
    # Save canvas
    if canvas:
        img_data = base64.b64decode(canvas.split(',')[1])
        with open("solve_react.png", "wb") as f: f.write(img_data)
        print(f"[*] Saved ({len(img_data)} bytes)", flush=True)
    
    # API
    import requests
    proxy = {"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"}
    print("[*] Calling NopeCHA...", flush=True)
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
            time.sleep(15)
            for f in page.frames:
                print(f"  Frame: {f.url[:100]}", flush=True)
            print(f"Page URL: {page.url[:150]}", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        print(resp.text[:500], flush=True)
    
    input("Enter to close...")
    browser.close()
