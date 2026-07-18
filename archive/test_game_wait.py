"""Check enforcement iframe content and wait longer for game-core."""
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
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    page.click("#login-button")
    print("[*] Submitted", flush=True)
    
    # Wait for enforcement frame
    enf_frame = None
    for i in range(30):
        for f in page.frames:
            if 'enforcement' in f.url:
                enf_frame = f
                break
        if enf_frame:
            print(f"[+] Enforcement at {i}s", flush=True)
            break
        time.sleep(1)
    else:
        print("[-] No enforcement in 30s", flush=True)
        proc.kill()
        exit(1)
    
    # Wait for game-core (poll longer)
    game_frame = None
    for i in range(30):
        for f in page.frames:
            if 'game-core' in f.url:
                game_frame = f
                break
        if game_frame:
            print(f"[+] Game-core at {i}s after enforcement", flush=True)
            break
        
        # Check enforcement HTML for game type
        if i == 0 or i == 10:
            try:
                html = enf_frame.evaluate("() => (document.body?.innerHTML || '').slice(0, 2000)")
                print(f"  Enforcement HTML ({i}s): {html[:300]}", flush=True)
            except Exception as e:
                print(f"  HTML error: {e}", flush=True)
        
        time.sleep(1)
    else:
        print("[-] No game-core in 30s", flush=True)
        # Show all frame URLs
        for f in page.frames:
            print(f"  {f.url[:150]}", flush=True)
        
        # Try to get more info from enforcement iframe
        try:
            html = enf_frame.evaluate("() => document.body?.innerHTML || ''")
            print(f"\nEnforcement full HTML: {html[:2000]}", flush=True)
            text = enf_frame.evaluate("() => document.body?.innerText || ''")
            print(f"Enforcement text: {text[:500]}", flush=True)
        except Exception as e:
            print(f"Enforcement error: {e}", flush=True)
        
        proc.kill()
        exit(1)
    
    print(f"\nGame-core URL: {game_frame.url[:200]}", flush=True)
    
    # Try to understand the game type
    game_html = game_frame.evaluate("() => (document.body?.innerHTML || '').slice(0, 1000)")
    print(f"Game HTML: {game_html[:500]}", flush=True)
    
    # Canvas
    canvas = game_frame.evaluate("""() => {
        const c = document.querySelector('canvas');
        if (!c) return 'no-canvas';
        return `canvas ${c.width}x${c.height}`;
    }""")
    print(f"Canvas: {canvas}", flush=True)

proc.kill()
