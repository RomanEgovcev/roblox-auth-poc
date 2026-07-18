"""Test Chrome flags to enable SW registration for unpacked MV3 extensions."""
import os, time, subprocess, json

chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext_path = "C:\\Users\\regov\\Desktop\\lua\\test_ext_basic"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

import shutil

test_configs = [
    ("NO EXTRA FLAGS", []),
    ("--disable-features=DisableExtensionSW", ["--disable-features=DisableExtensionSW"]),
    ("--enable-features=ExtensionsManifestV3", ["--enable-features=ExtensionsManifestV3"]),
    ("--silent-debugger", ["--silent-debugger"]),
]

for label, extra_flags in test_configs:
    print(f"\n=== Testing: {label} ===")
    try:
        if os.path.exists(profile):
            shutil.rmtree(profile, ignore_errors=True)
    except:
        pass
    time.sleep(1)

    proc = subprocess.Popen(
        [chrome, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
         "--no-first-run", "--remote-debugging-port=9222",
         "--remote-allow-origins=*",
         "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"] + extra_flags,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(6)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        
        page.goto("chrome://serviceworker-internals", wait_until="domcontentloaded")
        time.sleep(2)
        
        text = page.evaluate("() => document.body.innerText")
        reg_count = text.count("Scope: chrome-extension://")
        print(f"  Registrations: {reg_count}")
        
        # Show all scopes
        for line in text.split("\n"):
            if "Scope: chrome-extension://" in line:
                print(f"  {line.strip()[:100]}")

    proc.kill()
    time.sleep(2)
