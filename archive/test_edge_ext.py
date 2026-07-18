"""Test Edge 139 with extension - check SW + captcha."""
import os, time, subprocess, json, sys

edge = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
ext = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_edge"

proc = subprocess.Popen(
    [edge, f"--user-data-dir={profile}", f"--load-extension={ext}",
     "--no-first-run", "--remote-debugging-port=9333",
     "--remote-allow-origins=*",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(6)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9333")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    # Check SW registrations
    cdp = ctx.new_cdp_session(page)
    cdp.send("ServiceWorker.enable")
    
    def on_sw(params):
        regs = params.get('registrations', [])
        for r in regs:
            scope = r.get('scopeURL', '')
            if 'dknlfmjaanfblgfdfebhijalfmhmjjjo' in scope:
                print(f"\n[!!!] NopeCHA SW REGISTERED in Edge!", flush=True)
                print(json.dumps(params, indent=2, default=str)[:500], flush=True)
    
    cdp.on("ServiceWorker.workerRegistrationUpdated", on_sw)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    page.click("#login-button")
    print("[*] Login submitted", flush=True)
    
    for i in range(60):
        frames = page.frames
        game = any('game-core' in f.url for f in frames)
        arkose = any('arkoselabs' in f.url for f in frames)
        
        if game:
            print(f"[+] Game-core at {i}s!", flush=True)
        
        # Check SW
        try:
            sw = cdp.send("ServiceWorker.getAllRegistrations")
            for r in sw.get('registrations', []):
                if 'dknlfmjaanfblgfdfebhijalfmhmjjjo' in r.get('scopeURL', ''):
                    print(f"[SW] NopeCHA registered! {json.dumps(r, default=str)[:300]}", flush=True)
        except Exception as e:
            print(f"  SW check error: {e}", flush=True)
        
        if game:
            time.sleep(5)
            print(f"URL: {page.url[:200]}", flush=True)
            print(f"Frames: {[f.url[:100] for f in frames]}", flush=True)
            break
        time.sleep(1)
    else:
        print("[-] No captcha in 60s", flush=True)
    
    # Final SW check
    try:
        sw = cdp.send("ServiceWorker.getAllRegistrations")
        print(f"\n=== All SW registrations ===", flush=True)
        print(json.dumps(sw, indent=2, default=str)[:1000], flush=True)
    except Exception as e:
        print(f"  SW error: {e}", flush=True)
    
    ss = page.screenshot()
    with open("edge_captcha.png", "wb") as img:
        img.write(ss)
    print(f"\nScreenshot: {len(ss)} bytes", flush=True)

proc.kill()
