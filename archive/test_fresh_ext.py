"""Fresh profile + extension + single login attempt."""
import os, time, subprocess, json

chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

import shutil
try:
    if os.path.exists(profile):
        shutil.rmtree(profile, ignore_errors=True)
except:
    pass

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
    page = ctx.new_page()
    
    responses = []
    page.on("response", lambda r: responses.append({"url": r.url[:150], "status": r.status}) 
             if "auth.roblox.com" in r.url else None)
    page.on("console", lambda msg: print(f"[C] {msg.text[:200]}"))
    page.on("framenavigated", lambda f: print(f"[F] {f.url[:150]}"))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    page.click("#login-button")
    print("[*] Login submitted", flush=True)
    
    time.sleep(10)
    
    print(f"\n=== Auth responses ===")
    for r in responses:
        print(f"  {r['status']} {r['url']}")
    
    print(f"\n=== All frames ===")
    for f in page.frames:
        url = f.url[:200]
        if 'roblox' in url or 'arkoselabs' in url or 'funcaptcha' in url:
            print(f"  {url}")

proc.kill()
