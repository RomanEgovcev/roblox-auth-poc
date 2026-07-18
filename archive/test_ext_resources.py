"""Check extension load and try accessing extension resources."""
import os, time, subprocess, json, requests

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

EXT_ID = "dknlfmjaanfblgfdfebhijalfmhmjjjo"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    # Enable console to catch errors
    errors = []
    def on_console(msg):
        if "error" in msg.text.lower() or "fail" in msg.text.lower() or "ERR_" in msg.text:
            loc = msg.location.get("url","")
            if "extension" in loc.lower() or "dknlfm" in loc or "nopecha" in msg.text.lower():
                errors.append(f"[ERR] {msg.text[:200]}")
    page.on("console", on_console)
    
    # Try navigating to extension's popup page
    page.goto(f"chrome-extension://{EXT_ID}/assets/ip10n8.html", wait_until="domcontentloaded", timeout=10000)
    time.sleep(2)
    print(f"=== Navigation error for popup ===")
    print(f"URL: {page.url}")
    content = page.evaluate("() => document.body?.innerText?.slice(0, 500) || 'no content'")
    print(f"Content: {content}")
    
    # Now try the extension's main page (might be different from popup)
    page.goto(f"chrome-extension://{EXT_ID}/assets/index.html", wait_until="domcontentloaded", timeout=10000)
    time.sleep(2)
    print(f"\n=== Navigation to index.html ===")
    print(f"URL: {page.url}")
    
    # Now try navigating to the SW file
    page.goto(f"chrome-extension://{EXT_ID}/assets/4ncg2v.js", wait_until="load", timeout=10000)
    time.sleep(2)
    print(f"\n=== Navigation to SW file ===")
    print(f"URL: {page.url}")
    text = page.evaluate("() => document.body?.innerText?.slice(0, 200) || document.body?.textContent?.slice(0, 200) || 'no content'")
    print(f"Content: {text}")
    
    # Try to check chrome.runtime from the page
    runtime = page.evaluate("""() => {
        try {
            if (chrome && chrome.runtime) {
                return {
                    id: chrome.runtime.id,
                    hasBackground: typeof chrome.runtime.getBackgroundPage !== 'undefined',
                };
            }
            return null;
        } catch(e) { return {error: e.message}; }
    }""")
    print(f"\n=== chrome.runtime from page ===")
    print(json.dumps(runtime, indent=2))
    
    print(f"\n=== Console errors ===")
    for e in errors:
        print(e)

proc.kill()
