"""Test: captcha on-demand, check SW registration, explore frames."""
import os, time, subprocess, json, sys

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
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    
    # Set up CDP for SW monitoring FIRST
    cdp = ctx.new_cdp_session(page)
    cdp.send("ServiceWorker.enable")
    
    def on_sw_reg(params):
        print(f"[SW] registration: {json.dumps(params, default=str)[:300]}", flush=True)
    
    def on_sw_ver(params):
        print(f"[SW] version: {json.dumps(params, default=str)[:300]}", flush=True)
    
    cdp.on("ServiceWorker.workerRegistrationUpdated", on_sw_reg)
    cdp.on("ServiceWorker.workerVersionUpdated", on_sw_ver)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Response monitoring
    responses = []
    page.on("response", lambda r: responses.append({"url": r.url[:150], "status": r.status}))
    
    page.click("#login-button")
    print("[*] Login submitted, polling for captcha...", flush=True)
    
    captcha_found = False
    for i in range(90):
        frames = page.frames
        for f in frames:
            url = f.url
            if 'arkoselabs' in url or 'funcaptcha' in url or 'game-core' in url:
                if not captcha_found:
                    print(f"[+] Captcha frame at {i}s: {url[:200]}", flush=True)
                    captcha_found = True
        if captcha_found:
            break
        # Check page text
        try:
            t = page.evaluate("() => (document.body?.innerText || '').slice(0, 500)")
            if 'verify' in t.lower() or 'captcha' in t.lower():
                print(f"[*] Text: {t[:200]}", flush=True)
        except:
            pass
        time.sleep(1)
    
    if not captcha_found:
        print("[-] No captcha in 90s", flush=True)
        print(f"URL: {page.url[:200]}", flush=True)
        print(f"Frames: {[f.url[:100] for f in page.frames]}", flush=True)
        auth = [r for r in responses if 'auth.roblox.com' in r['url']]
        if auth:
            print(f"Auth: {auth[-1]}")
        proc.kill()
        exit(1)
    
    # Check SW registrations NOW
    print("\n=== Service Worker registrations ===", flush=True)
    try:
        sw_result = cdp.send("ServiceWorker.getAllRegistrations")
        print(f"Registrations: {json.dumps(sw_result, indent=2, default=str)}", flush=True)
    except Exception as e:
        print(f"  SW error: {e}", flush=True)
    
    # List all frames
    print(f"\n=== Frame URLs ===")
    for f in page.frames:
        print(f"  {f.url[:200]}")
    
    # Screenshot
    ss = page.screenshot()
    with open("captcha_sw.png", "wb") as img:
        img.write(ss)
    print(f"\nScreenshot saved ({len(ss)} bytes)")
    
    # Explore game-core iframe if present
    for f in page.frames:
        if 'game-core' in f.url:
            try:
                html = f.evaluate("() => document.body?.innerHTML?.slice(0, 2000) || ''")
                print(f"\n=== Game-core HTML ===")
                print(html[:1500])
                # Check for canvas
                canvas = f.evaluate("""() => {
                    const c = document.querySelector('canvas');
                    if (!c) return 'no canvas';
                    return `canvas ${c.width}x${c.height}`;
                }""")
                print(f"Canvas: {canvas}")
            except Exception as e:
                print(f"  Game-core error: {e}")

proc.kill()
