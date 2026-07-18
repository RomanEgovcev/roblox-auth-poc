"""Test minimal extension with SW to verify --load-extension works."""
import os, time, subprocess, json, requests

chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
test_ext_path = "C:\\Users\\regov\\Desktop\\lua\\test_ext_sw"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

import shutil
try:
    if os.path.exists(profile):
        shutil.rmtree(profile, ignore_errors=True)
except:
    pass
time.sleep(1)

proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}", f"--load-extension={test_ext_path}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(6)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    
    # Check SW internals
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("chrome://serviceworker-internals", wait_until="domcontentloaded")
    time.sleep(3)
    
    text = page.evaluate("() => document.body.innerText")
    print("=== ServiceWorker Internals ===")
    print(text[:2000])
    
    # Check CDP targets
    targets = requests.get("http://localhost:9222/json").json()
    print(f"\n=== CDP Targets ({len(targets)}) ===")
    for t in targets:
        if t["type"] == "service_worker":
            url = t.get("url","")[:150]
            print(f"  SW: {url}")
    
    # Navigate to a page and see if content script + SW work
    page2 = ctx.new_page()
    page2.on("console", lambda msg: print(f"[CS] {msg.text[:200]}"))
    page2.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(5)
    
    # Check SW targets again
    targets2 = requests.get("http://localhost:9222/json").json()
    sw_targets = [t for t in targets2 if t["type"] == "service_worker"]
    print(f"\n=== SW targets after navigation: {len(sw_targets)} ===")
    for t in sw_targets:
        print(f"  {t.get('url','')[:100]}")
    
    page2.close()

proc.kill()
