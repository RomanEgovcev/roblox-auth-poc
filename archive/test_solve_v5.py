"""Solve captcha: warm profile first, then login with proper CSRF."""
import os, time, subprocess, json, base64, io

chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

# (killed externally before script run)

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
    
    # Phase 1: Warm up - visit page, wait for load
    print("[*] Warming up...", flush=True)
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(5)
    
    # Get CSRF token from cookies or meta
    csrf = page.evaluate("""() => {
        // Check meta tags
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.content;
        // Check data attributes
        const btn = document.querySelector('#login-button');
        if (btn) for (const attr of btn.attributes) {
            if (attr.name.includes('csrf') || attr.name.includes('token'))
                return attr.value;
        }
        return null;
    }""")
    print(f"CSRF meta: {csrf}", flush=True)
    
    # Also check cookies
    cookies = ctx.cookies("https://www.roblox.com")
    csrf_cookies = [c for c in cookies if 'csrf' in c['name'].lower()]
    print(f"CSRF cookies: {[(c['name'], c['value'][:20]) for c in csrf_cookies]}", flush=True)
    
    # Phase 2: Submit login via JS (not page.click - triggers proper CSRF)
    print("[*] Submitting login...", flush=True)
    result = page.evaluate("""async () => {
        try {
            const resp = await fetch('https://auth.roblox.com/v2/login', {
                method: 'POST',
                credentials: 'include',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    ctype: 'Username',
                    credential: 'testuser123',
                    password: 'wrongpass123!'
                })
            });
            return {status: resp.status, headers: Object.fromEntries(resp.headers.entries())};
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"Login result: {json.dumps(result, default=str)[:500]}", flush=True)
    
    # The above fetch might fail because page needs form submit.
    # Let's use the form instead
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    auth_responses = []
    page.on("response", lambda r: auth_responses.append({"url": r.url[:200], "status": r.status}))
    
    page.click("#login-button")
    print("[*] Form submitted", flush=True)
    
    # Poll for enforcement
    enf = None
    game = None
    for i in range(90):
        auth_resp = [r for r in auth_responses if 'auth.roblox.com' in r['url']]
        auth_status = str(auth_resp[-1]['status']) if auth_resp else 'none'
        
        for f in page.frames:
            if 'enforcement' in f.url:
                enf = f
            if 'game-core' in f.url:
                game = f
        
        if i % 10 == 0:
            print(f"[{i}s] auth:{auth_status} frames:{len(page.frames)} game:{bool(game)} enf:{bool(enf)}", flush=True)
            print(f"  URLs: {[f.url[:80] for f in page.frames]}", flush=True)
        
        if enf and game:
            print(f"[+] Both frames at {i}s (auth:{auth_status})", flush=True)
            break
        
        time.sleep(1)
    else:
        print("[-] No frames in 90s", flush=True)
        # Check if login error shown
        error = page.evaluate("() => document.querySelector('.error, .alert, [class*=error]')?.textContent || 'none'")
        print(f"Error: {error}", flush=True)
        proc.kill(); exit(1)
    
    # Now extract and solve
    print("\n[*] Waiting for game to initialize...", flush=True)
    for wait_i in range(30):
        cinfo = None
        for fname, f in [('game-core', game), ('enforcement', enf)]:
            cinfo = f.evaluate("""() => {
                const c = document.querySelector('canvas');
                if (!c) return null;
                return {w: c.width, h: c.height, tag: c.tagName};
            }""")
            if cinfo:
                print(f"[{wait_i}s] {fname} canvas: {cinfo}", flush=True)
                break
        if cinfo:
            break
        time.sleep(1)
    else:
        print("[-] No canvas appeared", flush=True)
        # Save screenshot anyway
        ss = page.screenshot()
        with open("debug_state.png", "wb") as f:
            f.write(ss)
        print("Saved debug_state.png", flush=True)
        proc.kill(); exit(1)
    
    # Get task text
    task = enf.evaluate("""() => {
        const every = document.querySelectorAll('*');
        for (const e of every) {
            const t = (e.textContent || '').trim();
            if (t.length > 5 && t.length < 300) return t;
        }
        return 'none';
    }""")
    print(f"Task: {task[:300]}", flush=True)
    
    # Get canvas data
    canvas = None
    for fname, f in [('game-core', game), ('enforcement', enf)]:
        cdata = f.evaluate("""() => {
            const c = document.querySelector('canvas');
            if (!c) return null;
            try { return c.toDataURL('image/png'); }
            catch(e) { return '__tainted__'; }
        }""")
        if cdata and cdata != '__tainted__':
            canvas = cdata
            print(f"[+] Canvas from {fname} via toDataURL", flush=True)
            break
        elif cdata == '__tainted__':
            print(f"[!] {fname} canvas tainted", flush=True)
    
    if not canvas:
        from PIL import Image
        rect = game.evaluate("""() => {
            const c = document.querySelector('canvas');
            if (!c) return null;
            const r = c.getBoundingClientRect();
            let x = r.x, y = r.y;
            try {
                let frame = window;
                while (frame.frameElement) {
                    const fr = frame.frameElement.getBoundingClientRect();
                    x += fr.x; y += fr.y;
                    frame = frame.parent;
                }
            } catch(e) {}
            return {x: x, y: y, w: r.width, h: r.height};
        }""")
        if rect and rect['w'] > 10:
            ss = page.screenshot()
            img = Image.open(io.BytesIO(ss))
            r = rect
            cr = img.crop((r['x'], r['y'], r['x']+r['w'], r['y']+r['h']))
            buf = io.BytesIO(); cr.save(buf, format='PNG')
            canvas = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
            print(f"[+] Canvas via page crop", flush=True)
        else:
            ss = page.screenshot()
            canvas = 'data:image/png;base64,' + base64.b64encode(ss).decode()
            print(f"[!] Full page fallback", flush=True)
    
    img_data = base64.b64decode(canvas.split(',')[1])
    with open("solve_result.png", "wb") as f:
        f.write(img_data)
    print(f"[*] Saved solve_result.png ({len(img_data)} bytes)", flush=True)
    
    # Call API
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
            page_url = page.url
            print(f"URL: {page_url[:200]}", flush=True)
            if 'home' in page_url.lower():
                print("\n[!!!] CAPTCHA SOLVED!", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        print(resp.text[:500], flush=True)

proc.kill()
