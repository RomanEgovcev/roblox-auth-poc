"""Test: Chrome 150 without extension, just btn.click() evaluate."""
import os, time, subprocess, json

chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile2"

# Kill old Chrome
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

# Remove old profile
import shutil
try: shutil.rmtree(profile)
except: pass

# Start Chrome WITHOUT extension
proc = subprocess.Popen(
    [chrome, f"--user-data-dir={profile}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(6)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(5)
    
    # Fill
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Track requests
    requests_log = []
    page.on("response", lambda r: requests_log.append({"url": r.url[:150], "status": r.status}))
    
    # btn.click() via evaluate
    page.evaluate("document.querySelector('#login-button')?.click()")
    print("[*] Clicked via btn.click()", flush=True)
    
    time.sleep(5)
    
    # Check for auth request
    auth_reqs = [r for r in requests_log if 'auth.roblox' in r['url']]
    print(f"Auth responses: {auth_reqs}", flush=True)
    
    if not auth_reqs:
        print("[!] NO AUTH - Chrome 150 issue or CDP issue", flush=True)
        # Also try page.click as fallback
        page.click("#login-button")
        time.sleep(3)
        auth_reqs2 = [r for r in requests_log if 'auth.roblox' in r['url']]
        print(f"After page.click: {[(r['url'][:80], r['status']) for r in requests_log if 'login' in r['url'] or 'auth' in r['url']]}", flush=True)
    else:
        print(f"[+] Auth response: {auth_reqs[0]['status']}", flush=True)
    
    # Check page state
    print(f"URL: {page.url[:150]}", flush=True)
    error = page.evaluate("() => document.querySelector('.alert, [class*=error], [class*=alert]')?.textContent || 'none'")
    print(f"Error: {error}", flush=True)

proc.kill()
