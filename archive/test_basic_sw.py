"""Create minimal test extension and check SW registration."""
import os, time, subprocess, json, shutil

ext_dir = "C:\\Users\\regov\\Desktop\\lua\\test_ext_basic"
if os.path.exists(ext_dir):
    shutil.rmtree(ext_dir, ignore_errors=True)
os.makedirs(ext_dir, exist_ok=True)

# Manifest
with open(os.path.join(ext_dir, "manifest.json"), "w") as f:
    f.write('{"manifest_version":3,"name":"Basic SW","version":"1.0","background":{"service_worker":"bg.js"},"permissions":["storage"]}')

# SW
with open(os.path.join(ext_dir, "bg.js"), "w") as f:
    f.write('console.log("Basic SW started");')

time.sleep(0.5)

chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

try:
    if os.path.exists(profile):
        shutil.rmtree(profile, ignore_errors=True)
except:
    pass
time.sleep(1)

proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_dir}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(8)

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
    
    # Check if our extension's scope exists
    if ext_dir.replace("\\","/").split("/")[-1] in text or "Basic" in text:
        print("\n=== OUR EXTENSION FOUND in SW list! ===")
    else:
        print("\n=== Our extension NOT in SW list ===")

proc.kill()
