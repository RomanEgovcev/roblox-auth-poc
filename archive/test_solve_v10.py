"""Solve: React-compatible form fill + click, then solve captcha."""
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
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(5)
    
    # Fill inputs using React-compatible method
    print("[*] Filling form via React...", flush=True)
    page.evaluate("""() => {
        const setValue = (selector, value) => {
            const input = document.querySelector(selector);
            if (!input) return;
            const proto = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
            const setter = proto.set;
            setter.call(input, value);
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
        };
        setValue("input[name='username']", "testuser123");
        setValue("input[name='password']", "wrongpass123!");
    }""")
    
    # Now try click - capture network
    auth_responses = []
    page.on("response", lambda r: auth_responses.append({"url": r.url[:200], "status": r.status}))
    
    print("[*] Clicking login...", flush=True)
    page.click("#login-button")
    
    # Poll
    enf = None; game = None
    for i in range(90):
        auth_resp = [r for r in auth_responses if 'auth.roblox.com' in r['url']]
        auth_status = str(auth_resp[-1]['status']) if auth_resp else 'none'
        
        for f in page.frames:
            if 'enforcement' in f.url: enf = f
            if 'game-core' in f.url: game = f
        
        if i % 10 == 0:
            print(f"[{i}s] auth:{auth_status} frames:{len(page.frames)} game:{bool(game)} enf:{bool(enf)}", flush=True)
        
        if enf and game:
            print(f"[+] Both at {i}s (auth:{auth_status})", flush=True)
            break
        time.sleep(1)
    else:
        # Check all responses and page state
        print(f"[-] No frames. Auth responses: {[(r['url'][:60], r['status']) for r in auth_responses]}", flush=True)
        page_url = page.url
        print(f"URL: {page_url[:200]}", flush=True)
        if 'search' in page_url:
            print("[!] Button navigated to search - React state not updated", flush=True)
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
    
    task = enf.evaluate("""() => {
        const every = document.querySelectorAll('*');
        for (const e of every) { const t = (e.textContent || '').trim(); if (t.length > 5 && t.length < 300) return t; }
        return 'none';
    }""")
    print(f"Task: {task[:300]}", flush=True)
    
    img_data = base64.b64decode(canvas.split(',')[1])
    with open("solve_result.png", "wb") as f: f.write(img_data)
    print(f"[*] Saved solve_result.png ({len(img_data)} bytes)", flush=True)
    
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

proc.kill()
