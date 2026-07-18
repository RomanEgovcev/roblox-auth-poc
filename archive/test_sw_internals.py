"""Check service worker registration status."""
import os, time, subprocess, json

chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext_path = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

import shutil
if os.path.exists(profile):
    shutil.rmtree(profile)
time.sleep(1)

proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
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
    
    page.goto("chrome://serviceworker-internals", wait_until="domcontentloaded")
    time.sleep(3)
    
    text = page.evaluate("() => document.body.innerText")
    print("=== ServiceWorker Internals ===")
    print(text[:3000])

    # Also navigate to extensions page to check status
    page.goto("chrome://extensions", wait_until="domcontentloaded")
    time.sleep(2)
    text2 = page.evaluate("() => document.body.innerText")
    # Filter for nopecha
    for line in text2.split("\n"):
        if "nopecha" in line.lower() or "dknlfm" in line:
            print(f"EXT: {line.strip()[:200]}")

proc.kill()
