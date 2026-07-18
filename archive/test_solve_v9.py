"""Solve: proper fetch login with CSRF retry, then extract captcha."""
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
time.sleep(8)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    # Visit login page to set up session
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(5)
    
    # Get initial CSRF via a deliberate 403
    print("[*] Getting CSRF token...", flush=True)
    csrf_token = page.evaluate("""async () => {
        const resp = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST',
            credentials: 'include',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({"ctype": "Username", "credential": "test", "password": "test"})
        });
        const h = resp.headers.get('x-csrf-token');
        const body = await resp.text();
        return {csrf: h, status: resp.status, body: body.slice(0, 300)};
    }""")
    print(f"CSRF result: {json.dumps(csrf_token, default=str)[:300]}", flush=True)
    
    if not csrf_token.get('csrf'):
        print("[-] No CSRF token", flush=True)
        proc.kill(); exit(1)
    
    csrf = csrf_token['csrf']
    print(f"[+] CSRF: {csrf}", flush=True)
    
    # Now try login with different payload formats
    payloads = [
        {"ctype": "Username", "credential": "testuser123", "password": "wrongpass123!"},
        {"ctype": "username", "credential": "testuser123", "password": "wrongpass123!"},
        {"username": "testuser123", "password": "wrongpass123!"},
    ]
    
    login_result = None
    for pi, payload in enumerate(payloads):
        result = page.evaluate(f"""async () => {{
            const resp = await fetch('https://auth.roblox.com/v2/login', {{
                method: 'POST',
                credentials: 'include',
                headers: {json.dumps({'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf})},
                body: JSON.stringify({json.dumps(payload)})
            }});
            const text = await resp.text();
            return {{status: resp.status, body: text.slice(0, 500), headers: Object.fromEntries(resp.headers.entries())}};
        }}""")
        print(f"Payload {pi}: status={result['status']}", flush=True)
        print(f"  body: {result.get('body', '')[:200]}", flush=True)
        if result['status'] == 403 and 'challenge' in result.get('body', '').lower():
            login_result = result
            print("  -> 403 WITH CHALLENGE!", flush=True)
            break
        elif result['status'] == 200:
            print("  -> Login OK!", flush=True)
            break
        elif result['status'] == 429:
            print("  -> Rate limited!", flush=True)
            break
    
    if not login_result:
        print("[-] No successful login", flush=True)
        # Try form submit as fallback (using type instead of fill)
        print("[*] Trying page.type()...", flush=True)
        page.type("input[name='username']", "testuser123")
        page.type("input[name='password']", "wrongpass123!")
        
        auth_responses = []
        page.on("response", lambda r: auth_responses.append({"url": r.url[:200], "status": r.status}))
        page.click("#login-button")
        print("[*] Submitted via type+click", flush=True)
    
    # Poll for enforcement + game-core
    enf = None; game = None
    for i in range(90):
        for f in page.frames:
            if 'enforcement' in f.url: enf = f
            if 'game-core' in f.url: game = f
        if enf and game:
            print(f"[+] Both at {i}s", flush=True)
            break
        if i % 10 == 0:
            print(f"[{i}s] frames:{len(page.frames)} game:{bool(game)} enf:{bool(enf)} urls:{[f.url[:60] for f in page.frames]}", flush=True)
        time.sleep(1)
    else:
        print("[-] No frames", flush=True)
        proc.kill(); exit(1)
    
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
        proc.kill(); exit(1)
    
    # Get task
    task = enf.evaluate("""() => {
        const every = document.querySelectorAll('*');
        for (const e of every) { const t = (e.textContent || '').trim(); if (t.length > 5 && t.length < 300) return t; }
        return 'none';
    }""")
    print(f"Task: {task[:300]}", flush=True)
    
    img_data = base64.b64decode(canvas.split(',')[1])
    with open("solve_result.png", "wb") as f: f.write(img_data)
    print(f"[*] Saved solve_result.png ({len(img_data)} bytes)", flush=True)
    
    # API call
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
