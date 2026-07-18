"""Check SW registration after removing type:module from manifest."""
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
time.sleep(8)

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
    # Look for our extension ID
    if "dknlfm" in text:
        lines = [l for l in text.split("\n") if "dknlfm" in l.lower()]
        print(f"Found NopeCHA SW!")
        for l in lines:
            print(f"  {l[:200]}")
    else:
        print(text[:2000])
    
    # Also check all CDP targets
    import requests
    targets = requests.get("http://localhost:9222/json").json()
    print(f"\n=== CDP Targets ({len(targets)}) ===")
    for t in targets:
        url = t.get("url", "")[:100]
        if "nopecha" in url.lower() or "dknlfm" in url or t["type"] == "service_worker":
            print(f"  type={t['type']:16s} url={url}")

proc.kill()
