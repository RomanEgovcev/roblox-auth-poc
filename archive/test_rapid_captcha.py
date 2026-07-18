"""Multiple rapid attempts to trigger captcha WITH extension loaded."""
import os, time, subprocess, json

chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext_path = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

import shutil
try:
    if os.path.exists(profile):
        shutil.rmtree(profile, ignore_errors=True)
except:
    pass

proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
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
    
    page.on("framenavigated", lambda f: print(f"[F] {f.url[:150]}"))
    requests_made = []
    
    def log_req(req):
        url = req.url
        if 'auth.roblox.com' in url or 'arkoselabs' in url:
            print(f"[R] {req.method} {url[:150]}")
    def log_resp(resp):
        url = resp.url
        if 'auth.roblox.com' in url:
            print(f"[RSP] {resp.status} {url[:150]}")
    page.on("request", log_req)
    page.on("response", log_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    
    # Rapid login attempts
    for attempt in range(30):
        try:
            page.fill("input[name='username']", "testuser123")
            page.fill("input[name='password']", "wrongpass123!")
            page.click("#login-button")
            
            # Check for captcha frames
            for f in page.frames:
                if 'arkoselabs' in f.url:
                    print(f"\n[+] CAPTCHA FOUND at attempt {attempt}!")
                    print(f"  Frame URL: {f.url[:200]}")
                    # Save screenshot
                    try:
                        ss = page.screenshot()
                        with open(f"captcha_{attempt}.png", "wb") as img:
                            img.write(ss)
                        print(f"  Screenshot saved to captcha_{attempt}.png")
                    except:
                        pass
                    # Now try to extract data and call API...
                    input("Press Enter to exit")
                    proc.kill()
                    exit()
        except Exception as e:
            print(f"  [E] attempt {attempt}: {e}")
        
        if attempt % 5 == 0:
            print(f"  [{attempt}] attempts done...")
        time.sleep(0.3)
    
    print("[-] No captcha in 30 attempts")

proc.kill()
