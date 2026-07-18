"""Test Edge 139 with extension (manual launch, no --disable-extensions)."""
import os, time, subprocess, json, sys

edge = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
ext = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_edge3"

proc = subprocess.Popen(
    [edge, f"--user-data-dir={profile}", f"--load-extension={ext}",
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
    
    # Check SW registrations
    cdp = ctx.new_cdp_session(page)
    cdp.send("ServiceWorker.enable")
    time.sleep(2)
    
    try:
        sw = cdp.send("ServiceWorker.getAllRegistrations")
        print(f"=== Initial SW registrations ===", flush=True)
        for r in sw.get('registrations', []):
            scope = r.get('scopeURL', '')
            print(f"  {scope}", flush=True)
        has_nopecha = any('dknlfmjaanfblgfdfebhijalfmhmjjjo' in r.get('scopeURL', '') for r in sw.get('registrations', []))
        print(f"  NopeCHA SW registered: {has_nopecha}", flush=True)
    except Exception as e:
        print(f"  SW error: {e}", flush=True)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    page.click("#login-button")
    print("[*] Login submitted, waiting...", flush=True)
    
    captcha_solved = False
    for i in range(60):
        frames = page.frames
        game = any('game-core' in f.url for f in frames)
        
        # Check if page redirected away from login
        if 'home' in page.url.lower() or 'games' in page.url.lower():
            print(f"[+] REDIRECT to {page.url[:150]} at {i}s - CAPTCHA SOLVED!", flush=True)
            captcha_solved = True
            break
        
        # Check for password error (meaning captcha wasn't required)
        try:
            page_text = page.evaluate("() => document.body?.innerText?.slice(0, 500) || ''")
            if 'Invalid' in page_text or 'incorrect' in page_text.lower():
                print(f"[*] Login error (no captcha needed) at {i}s", flush=True)
                break
        except:
            pass
        
        if game and i < 40:
            # Captcha appeared but we're still waiting
            if i % 5 == 0:
                print(f"  [{i}] Game-core visible, waiting for solve...", flush=True)
        
        time.sleep(1)
    else:
        print("[-] Timeout - 60s reached", flush=True)
        print(f"URL: {page.url[:200]}", flush=True)
        print(f"Game-core present: {any('game-core' in f.url for f in page.frames)}", flush=True)
    
    # Final SW check
    try:
        sw = cdp.send("ServiceWorker.getAllRegistrations")
        print(f"\n=== Final SW registrations ===", flush=True)
        for r in sw.get('registrations', []):
            scope = r.get('scopeURL', '')
            status = r.get('status', '')
            print(f"  scope={scope} status={status}", flush=True)
            if 'dknlfmjaanfblgfdfebhijalfmhmjjjo' in scope:
                print("  [!!!] NopeCHA SW IS REGISTERED!", flush=True)
    except Exception as e:
        print(f"SW final: {e}", flush=True)
    
    if captcha_solved:
        print("\n[SUCCESS] Captcha was solved automatically by Edge + extension!", flush=True)
    else:
        print("\n[FAIL] Captcha not solved.", flush=True)

proc.kill()
