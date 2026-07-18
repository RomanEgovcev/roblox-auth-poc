"""Trigger captcha with existing profile + extension + multiple attempts."""
import os, time, subprocess, json

chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

# DO NOT delete profile - use existing

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
    
    page.on("framenavigated", lambda f: print(f"[F] {f.url[:150]}"))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    
    for attempt in range(30):
        try:
            page.fill("input[name='username']", "testuser123")
            page.fill("input[name='password']", "wrongpass123!")
            page.click("#login-button")
            
            for _ in range(5):
                time.sleep(1)
                for f in page.frames:
                    if 'arkoselabs' in f.url:
                        print(f"\n[+] CAPTCHA at attempt {attempt}!")
                        print(f"  URL: {f.url[:200]}")
                        
                        # Explore the iframe structure
                        gf = [f2 for f2 in page.frames if 'game-core' in f2.url]
                        print(f"  Game frames: {len(gf)}")
                        
                        # Try to get task text
                        task = f.evaluate("""() => {
                            const all = document.querySelectorAll('*');
                            for (const el of all) {
                                if (el.textContent && el.textContent.length > 10 && 
                                    (el.textContent.includes('arrow') || el.textContent.includes('rotate') ||
                                     el.textContent.includes('click') || el.textContent.includes('hand'))) {
                                    return el.textContent.slice(0, 300);
                                }
                            }
                            return 'no task';
                        }""")
                        print(f"  Task: {task}")
                        
                        # Take screenshot of the captcha
                        ss = page.screenshot()
                        with open(f"captcha_attempt_{attempt}.png", "wb") as img:
                            img.write(ss)
                        print(f"  Screenshot saved")
                        
                        time.sleep(5)
                        proc.kill()
                        exit()
        except Exception as e:
            print(f"  [E] attempt {attempt}: {e}")
        
        if attempt % 5 == 0:
            print(f"  [{attempt}] attempts...")

print("[-] No captcha in 30 attempts")
proc.kill()
