"""Install NopeCHA extension into Chrome profile (simulate proper installation)."""
import json, os, shutil, subprocess, time

ext_id = "dknlfmjaanfblgfdfebhijalfmhmjjjo"
ext_src = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile_dir = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

# Create fresh profile
if os.path.exists(profile_dir):
    shutil.rmtree(profile_dir, ignore_errors=True)
time.sleep(1)

# Start Chrome once to initialize the profile
chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile_dir}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(5)
proc.kill()
time.sleep(2)

# Now manually install the extension
# 1. Copy extension files to the Extensions directory
ext_install_dir = os.path.join(profile_dir, "Default", "Extensions", ext_id, "0.6.1_0")
os.makedirs(ext_install_dir, exist_ok=True)

# Copy all files from source
for item in os.listdir(ext_src):
    s = os.path.join(ext_src, item)
    d = os.path.join(ext_install_dir, item)
    if os.path.isdir(s):
        shutil.copytree(s, d, dirs_exist_ok=True)
    else:
        shutil.copy2(s, d)

print(f"Extension copied to: {ext_install_dir}")

# 2. Add extension to Preferences
prefs_path = os.path.join(profile_dir, "Default", "Preferences")
with open(prefs_path, "r", encoding="utf-8") as f:
    prefs = json.load(f)

# Read the extension's manifest to include in settings
with open(os.path.join(ext_install_dir, "manifest.json"), "r") as f:
    manifest = json.load(f)

# Create extension settings
ext_settings = {
    "dknlfmjaanfblgfdfebhijalfmhmjjjo": {
        "state": 1,
        "location": 3,
        "path": ext_install_dir,
        "manifest": manifest,
        "was_installed_by_oem": False,
        "install_time": "13000000000000000"
    }
}

# Merge with existing settings
if "extensions" not in prefs:
    prefs["extensions"] = {}
if "settings" not in prefs["extensions"]:
    prefs["extensions"]["settings"] = {}

# Check if settings exist
existing_settings = prefs["extensions"].get("settings", {})
existing_settings.update(ext_settings)
prefs["extensions"]["settings"] = existing_settings

# Ensure other required keys exist
prefs["extensions"]["alerts"] = prefs.get("extensions", {}).get("alerts", {})
prefs["extensions"]["chrome_url_overrides"] = prefs.get("extensions", {}).get("chrome_url_overrides", {})
prefs["extensions"]["last_chrome_version"] = "150.0.7871.101"

with open(prefs_path, "w", encoding="utf-8") as f:
    json.dump(prefs, f, indent=2, ensure_ascii=False)

print("Extension added to Preferences")

# 3. Verify installation
for root, dirs, files in os.walk(ext_install_dir):
    for file in files:
        fp = os.path.join(root, file)
        print(f"  Installed: {fp[len(ext_install_dir)+1:]} ({os.path.getsize(fp)} bytes)")

print("\nExtension installed. Starting Chrome to verify...")

# 4. Start Chrome and check if extension loads and SW registers
proc2 = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile_dir}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(8)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    
    # Check CDP targets for SW
    import requests
    targets = requests.get("http://localhost:9222/json").json()
    print(f"\nCDP targets ({len(targets)}):")
    for t in targets:
        if t["type"] == "service_worker":
            print(f"  SW: {t.get('url','')[:150]}")
        if ext_id in t.get("url", ""):
            print(f"  EXT: type={t['type']} url={t.get('url','')[:100]}")
    
    # Check ServiceWorker internals
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("chrome://serviceworker-internals", wait_until="domcontentloaded")
    time.sleep(3)
    
    text = page.evaluate("() => document.body.innerText")
    print(f"\n=== ServiceWorker Internals ===")
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if ext_id in line or "Scope: chrome-extension://" in line:
            # Show context around this line
            for l in lines[max(0,i-1):i+5]:
                print(f"  {l.strip()[:200]}")
    
    # Navigate to a page and check extension content script
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    
    # Check for extension console messages  
    page.on("console", lambda msg: print(f"[C] {msg.text[:200]}"))
    
    # Try to detect extension presence
    has_nopecha = page.evaluate("""() => {
        try {
            return chrome?.runtime?.id === 'dknlfmjaanfblgfdfebhijalfmhmjjjo';
        } catch(e) { return false; }
    }""")
    print(f"\nExtension detected in page: {has_nopecha}")
    
    # Check targets again after navigation
    targets2 = requests.get("http://localhost:9222/json").json()
    sw_found = [t for t in targets2 if t["type"] == "service_worker" and ext_id in t.get("url","")]
    print(f"NopeCHA SW targets: {len(sw_found)}")

proc2.kill()
