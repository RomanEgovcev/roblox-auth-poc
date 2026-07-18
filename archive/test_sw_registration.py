"""Check if NopeCHA extension SW is registered (even if inactive) via CDP."""
import os, time, subprocess, json, requests

chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext_path = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

import shutil
try:
    if os.path.exists(profile):
        shutil.rmtree(profile, ignore_errors=True)
except:
    pass
time.sleep(1)

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
    
    cdp = page.context.new_cdp_session(page)
    cdp.send("ServiceWorker.enable")
    
    all_registrations = []
    def on_reg(params):
        for reg in params.get("registrations", []):
            url = reg.get("scopeURL", "")
            all_registrations.append(url)
    cdp.on("ServiceWorker.workerRegistrationUpdated", on_reg)
    
    print("Waiting for SW registrations (15s)...")
    time.sleep(15)
    
    print(f"\n=== All SW registrations ({len(all_registrations)}) ===")
    for r in all_registrations:
        print(f"  scope: {r}")
        
    # Check specifically for NopeCHA extension
    ext_id = "dknlfmjaanfblgfdfebhijalfmhmjjjo"
    found = [r for r in all_registrations if ext_id in r]
    print(f"\nNopeCHA registrations: {len(found)}")
    
    # Also try to get all worker registrations from the browser
    targets = requests.get("http://localhost:9222/json").json()
    print(f"\nCDP targets:")
    for t in targets:
        print(f"  type={t['type']:16s} url={t.get('url','')[:100]}")
    
    # Console check for extension errors
    page2 = ctx.new_page()
    page2.on("console", lambda msg: print(f"[C] {msg.text[:200]}"))
    page2.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    page2.fill("input[name='username']", "testuser123")
    page2.fill("input[name='password']", "wrongpass123!")
    page2.click("#login-button")
    time.sleep(10)
    
    # Check registrations again
    print(f"\n=== Registrations after login ({len(all_registrations)}) ===")
    for r in all_registrations:
        print(f"  scope: {r}")
    
    # Try to check via chrome.runtime from within a page
    try:
        ext_info = page2.evaluate("""() => {
            try {
                // Check if the NopeCHA extension is accessible
                const v = chrome?.runtime?.id;
                return {runtimeId: v || 'none'};
            } catch(e) {
                return {error: e.message};
            }
        }""")
        print(f"\nchrome.runtime: {ext_info}")
    except Exception as e:
        print(f"evaluate error: {e}")

proc.kill()
