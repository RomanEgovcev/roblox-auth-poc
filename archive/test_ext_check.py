"""Check extension load status."""
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
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions",
     "--enable-logging=stderr", "--v=1"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(5)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    
    # Check extensions page
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("chrome://extensions", wait_until="domcontentloaded")
    time.sleep(3)
    
    text = page.evaluate("() => document.body.innerText")
    print("=== chrome://extensions (first 3000 chars) ===")
    print(text[:3000])
    
    # Try to check for errors on the extension
    # Look for any sections mentioning errors or our extension
    error_divs = page.evaluate("""() => {
        const divs = document.querySelectorAll('div');
        return Array.from(divs).filter(d => d.textContent.includes('NopeCHA') || d.textContent.includes('dknlfm')).map(d => d.textContent.slice(0, 200));
    }""")
    print(f"\n=== Matches for NopeCHA ===")
    for i, d in enumerate(error_divs):
        print(f"  [{i}] {d}")

    # Try to get extension ID list from the page
    ids = page.evaluate("""() => {
        const items = document.querySelectorAll('extensions-manager');
        console.log('items:', items.length);
        return Array.from(items).map(i => i.textContent.slice(0, 200));
    }""")
    print(f"\n=== Extensions manager ===")
    print(ids[:5])

proc.kill()
