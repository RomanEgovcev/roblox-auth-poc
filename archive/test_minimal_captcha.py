"""Minimal test: trigger captcha, show all frames."""
import os, time, subprocess

chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

import shutil
try:
    if os.path.exists(profile):
        shutil.rmtree(profile, ignore_errors=True)
except:
    pass

proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(5)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    page.on("console", lambda msg: print(f"[C] {msg.text[:200]}"))
    page.on("framenavigated", lambda f: print(f"[F] {f.url[:150]}"))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    page.click("#login-button")
    print("[*] Clicked login", flush=True)
    
    for i in range(30):
        fs = page.frames
        print(f"  [{i}s] frames: {len(fs)}", flush=True)
        for f in fs:
            url = f.url[:200]
            if 'roblox' in url or 'arkoselabs' in url or 'funcaptcha' in url:
                print(f"    -> {url}")
        time.sleep(1)

proc.kill()
