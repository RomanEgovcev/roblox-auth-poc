"""Check ServiceWorker status via CDP ServiceWorker domain."""
import os, time, subprocess, json

chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext_path = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

import shutil
if os.path.exists(profile):
    shutil.rmtree(profile)
time.sleep(0.5)

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
    page = ctx.new_page()
    
    # Get a page CDP session
    cdp = page.context.new_cdp_session(page)
    
    # Enable ServiceWorker domain
    try:
        result = cdp.send("ServiceWorker.enable")
        print(f"ServiceWorker.enable: {result}")
    except Exception as e:
        print(f"ServiceWorker.enable failed: {e}")
    
    # Register callback for worker updates
    def on_worker_reg(params):
        print(f"[SW Registration]: {json.dumps(params)[:200]}")
    def on_worker_ver(params):
        print(f"[SW Version]: {json.dumps(params)[:300]}")
    def on_worker_err(params):
        print(f"[SW Error]: {json.dumps(params)[:300]}")
    
    cdp.on("ServiceWorker.workerRegistrationUpdated", on_worker_reg)
    cdp.on("ServiceWorker.workerVersionUpdated", on_worker_ver)
    cdp.on("ServiceWorker.workerErrorReported", on_worker_err)
    
    # Wait for any SW events
    print("Waiting for SW events (10s)...")
    time.sleep(10)
    
    # Now trigger a captcha page and see if SW wakes up
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    page.click("#login-button")
    print("Login submitted, waiting 15s for SW...")
    
    # Monitor for more events
    time.sleep(15)
    
    # Check all registrations via the CDP
    try:
        registrations = cdp.send("ServiceWorker.getWorkerRegistration", {"scopeURL": f"chrome-extension://{ext_id}/"})
        print(f"GetWorkerRegistration: {registrations}")
    except Exception as e:
        print(f"GetWorkerRegistration failed: {e}")

proc.kill()
