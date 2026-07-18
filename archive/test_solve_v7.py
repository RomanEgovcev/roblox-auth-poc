"""Two-pass: warm profile first, then login for captcha solve."""
import os, time, subprocess, json, base64, io

chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

def launch():
    return subprocess.Popen(
        [chrome, f"--user-data-dir={profile}", f"--load-extension={ext}",
         "--no-first-run", "--remote-debugging-port=9222",
         "--remote-allow-origins=*",
         "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

from playwright.sync_api import sync_playwright

# === PASS 1: Warm up ===
print("="*50, "PASS 1: Warm up", "="*50, sep="\n", flush=True)
proc = launch()
time.sleep(6)

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    page.goto("https://www.roblox.com", wait_until="domcontentloaded")
    time.sleep(3)
    
    # Just visit the main page to set cookies
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    cookies = ctx.cookies("https://www.roblox.com")
    csrf_cookies = [c for c in cookies if 'csrf' in c['name'].lower() or 'session' in c['name'].lower()]
    print(f"Cookies after warmup: {[(c['name'], c['value'][:20]) for c in csrf_cookies]}", flush=True)
    print(f"Total cookies: {len(cookies)}", flush=True)

proc.kill()
time.sleep(3)

# === PASS 2: Login + captcha solve ===
print("="*50, "PASS 2: Solve", "="*50, sep="\n", flush=True)
proc = launch()
time.sleep(6)

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    
    # Fill and submit login
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    auth_responses = []
    page.on("response", lambda r: auth_responses.append({"url": r.url[:200], "status": r.status}))
    
    page.click("#login-button")
    print("[*] Login submitted", flush=True)
    
    # Poll for enforcement + game-core
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
        
        if enf and game:
            print(f"[+] Both at {i}s (auth:{auth_status})", flush=True)
            break
        
        time.sleep(1)
    else:
        print(f"[-] No frames in 90s", flush=True)
        print(f"All responses: {[(r['url'][:80], r['status']) for r in auth_responses[:10]]}", flush=True)
        print(f"Frames: {[f.url[:80] for f in page.frames]}", flush=True)
        # Save screenshot for debug
        page.screenshot(path="debug_fail.png")
        print("Saved debug_fail.png", flush=True)
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
                canvas = c;
                print(f"[{wait_i}s] Canvas from {fname}", flush=True);
                break
            elif c == '__tainted__':
                print(f"[{wait_i}s] {fname} tainted", flush=True)
        if canvas:
            break
        time.sleep(1)
    else:
        print("[-] No canvas", flush=True)
        page.screenshot(path="debug_nocanvas.png")
        proc.kill(); exit(1)
    
    # Get task
    task = enf.evaluate("""() => {
        const every = document.querySelectorAll('*');
        for (const e of every) {
            const t = (e.textContent || '').trim();
            if (t.length > 5 && t.length < 300) return t;
        }
        return 'none';
    }""")
    print(f"Task: {task[:300]}", flush=True)
    
    # Fallback: page screenshot + crop
    if canvas:
        img_data = base64.b64decode(canvas.split(',')[1])
        with open("solve_result.png", "wb") as f:
            f.write(img_data)
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
