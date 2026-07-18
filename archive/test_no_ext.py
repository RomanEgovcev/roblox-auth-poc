"""Test WITHOUT extension - fresh profile, check if captcha loads."""
import os, time, subprocess, json, sys, shutil

chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_no_ext"

if os.path.exists(profile):
    shutil.rmtree(profile)

proc = subprocess.Popen(
    [chrome, f"--user-data-dir={profile}",
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
    
    auth_status = [0]
    def on_resp(r):
        if 'auth.roblox.com' in r.url:
            auth_status[0] = r.status
            print(f"[!] Auth: {r.status}", flush=True)
    
    page.on("response", on_resp)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    page.click("#login-button")
    print("[*] Submitted", flush=True)
    
    for i in range(60):
        frames = page.frames
        arkose = any('arkoselabs' in f.url for f in frames)
        game = any('game-core' in f.url for f in frames)
        
        if arkose or game:
            t = 'game-core' if game else 'arkose'
            print(f"[+] {t} at {i}s! auth:{auth_status[0]}", flush=True)
            break
        
        if i == 30:
            # Try clicking login again after 30s
            try:
                page.click("#login-button")
                print(f"  Re-clicked at 30s")
            except:
                pass
        
        time.sleep(1)
    else:
        print(f"[-] No captcha in 60s. auth:{auth_status[0]}", flush=True)
        print(f"URL: {page.url[:200]}", flush=True)
        print(f"Frames: {[f.url[:100] for f in page.frames]}", flush=True)

proc.kill()
