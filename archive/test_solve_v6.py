"""Solve: manual fetch with CSRF token, then extract captcha."""
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
    
    # Warm up
    print("[*] Warming up...", flush=True)
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(5)
    
    # Step 1: Get CSRF token via fetch (first call returns 403 with token)
    csrf_token = page.evaluate("""async () => {
        const resp = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST',
            credentials: 'include',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ctype: 'Username', credential: 'test', password: 'test'})
        });
        return resp.headers.get('x-csrf-token') || 'no_token';
    }""")
    print(f"CSRF: {csrf_token}", flush=True)
    
    if csrf_token == 'no_token':
        print("[-] No CSRF token, trying form submit as fallback", flush=True)
        page.fill("input[name='username']", "testuser123")
        page.fill("input[name='password']", "wrongpass123!")
        
        auth_responses = []
        page.on("response", lambda r: auth_responses.append({"url": r.url[:200], "status": r.status}))
        page.click("#login-button")
    else:
        # Step 2: Actual login with CSRF token
        result = page.evaluate(f"""async () => {{
            const resp = await fetch('https://auth.roblox.com/v2/login', {{
                method: 'POST',
                credentials: 'include',
                headers: {json.dumps({'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf_token})},
                body: JSON.stringify({{ctype: 'Username', credential: 'testuser123', password: 'wrongpass123!'}})
            }});
            const text = await resp.text();
            return {{status: resp.status, body: text.slice(0, 500), headers: Object.fromEntries(resp.headers.entries())}};
        }}""")
        print(f"Login: status={result['status']}", flush=True)
        print(f"  body: {result.get('body', '')[:300]}", flush=True)
        if 'x-csrf-token' in result.get('headers', {}):
            print(f"  CSRF in response: {result['headers']['x-csrf-token']}", flush=True)
    
    # Poll for enforcement + game-core
    enf = None
    game = None
    for i in range(90):
        for f in page.frames:
            if 'enforcement' in f.url:
                enf = f
            if 'game-core' in f.url:
                game = f
        if enf and game:
            print(f"[+] Both at {i}s", flush=True)
            break
        if i % 10 == 0:
            print(f"[{i}s] frames:{len(page.frames)} game:{bool(game)} enf:{bool(enf)}", flush=True)
            print(f"  URLs: {[f.url[:80] for f in page.frames]}", flush=True)
        time.sleep(1)
    else:
        print("[-] No frames", flush=True)
        proc.kill(); exit(1)
    
    # Wait for canvas to appear
    print("[*] Waiting for canvas...", flush=True)
    for wait_i in range(40):
        cinfo = None
        for fname, f in [('game-core', game), ('enforcement', enf)]:
            cinfo = f.evaluate("""() => {
                const c = document.querySelector('canvas');
                if (!c) return null;
                const r = c.getBoundingClientRect();
                return {w: c.width, h: c.height, rw: r.width, rh: r.height, rx: r.x, ry: r.y};
            }""")
            if cinfo:
                print(f"[{wait_i}s] {fname} canvas: {cinfo}", flush=True)
                break
        if cinfo:
            break
        time.sleep(1)
    else:
        print("[-] No canvas", flush=True)
        proc.kill(); exit(1)
    
    # Get task from enforcement
    task = enf.evaluate("""() => {
        const every = document.querySelectorAll('*');
        for (const e of every) {
            const t = (e.textContent || '').trim();
            if (t.length > 5 && t.length < 300) return t;
        }
        return 'none';
    }""")
    print(f"Task: {task[:300]}", flush=True)
    
    # Get canvas
    canvas = None
    for fname, f in [('game-core', game), ('enforcement', enf)]:
        c = f.evaluate("""() => {
            const el = document.querySelector('canvas');
            if (!el) return null;
            try {return el.toDataURL('image/png');} catch(e) {return '__tainted__';}
        }""")
        if c and c != '__tainted__':
            canvas = c;
            print(f"[+] Canvas from {fname}", flush=True);
            break
        elif c == '__tainted__':
            print(f"[!] {fname} tainted", flush=True)
    
    if not canvas:
        from PIL import Image
        rect = game.evaluate("""() => {
            const c = document.querySelector('canvas');
            if (!c) return null;
            const r = c.getBoundingClientRect();
            let x=r.x, y=r.y;
            try {
                let w=window;
                while (w.frameElement) {
                    const fr = w.frameElement.getBoundingClientRect();
                    x+=fr.x; y+=fr.y;
                    w = w.parent;
                }
            } catch(e) {}
            return {x, y, w: r.width, h: r.height};
        }""")
        if rect and rect['w'] > 10:
            ss = page.screenshot();
            img = Image.open(io.BytesIO(ss));
            cr = img.crop((rect['x'], rect['y'], rect['x']+rect['w'], rect['y']+rect['h']));
            buf = io.BytesIO(); cr.save(buf, format='PNG');
            canvas = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
        else:
            ss = page.screenshot();
            canvas = 'data:image/png;base64,' + base64.b64encode(ss).decode()
    
    img_data = base64.b64decode(canvas.split(',')[1])
    with open("solve_result.png", "wb") as f:
        f.write(img_data)
    print(f"[*] Saved solve_result.png ({len(img_data)} bytes)", flush=True)
    
    # NopeCHA API
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
            else:
                print(f"URL: {page.url[:200]}", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        print(resp.text[:500], flush=True)

proc.kill()
