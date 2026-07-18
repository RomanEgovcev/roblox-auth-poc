import os, time, subprocess, json, urllib.request

ext_path = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"

# Clear profile to avoid DNS caching issues
import shutil
if os.path.exists(profile):
    for item in os.listdir(profile):
        p = os.path.join(profile, item)
        if item != 'Default' or not os.path.isdir(p):
            continue
        default_dir = p

proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--proxy-server=socks5://127.0.0.1:10808",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("[*] Chrome launched (SOCKS5 :10808)", flush=True)
time.sleep(5)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = None
    for attempt in range(10):
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            print("[+] CDP connected", flush=True)
            break
        except:
            time.sleep(2)
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(15000)

    # Test 1: Navigation to nopecha.com
    print("[*] Test 1: Navigation to api.nopecha.com...", flush=True)
    try:
        page.goto("https://api.nopecha.com/v1/status", wait_until="domcontentloaded", timeout=15000)
        print(f"  Navigation OK: status={page.content()[:200]}", flush=True)
    except Exception as e:
        print(f"  Navigation FAILED: {e}", flush=True)

    # Test 2: Same-origin fetch (from api.nopecha.com)
    result = page.evaluate("""async () => {
        try {
            const resp = await fetch('/v1/status');
            const txt = await resp.text();
            return 'ok: ' + txt.slice(0, 100);
        } catch(e) {
            return 'error: ' + e.message;
        }
    }""")
    print(f"  Same-origin fetch from nopecha.com: {result}", flush=True)

    # Test 3: Cross-origin fetch from roblox.com to nopecha.com
    page.goto("https://www.roblox.com", wait_until="domcontentloaded", timeout=15000)
    result = page.evaluate("""async () => {
        try {
            const resp = await fetch('https://api.nopecha.com/v1/status');
            const txt = await resp.text();
            return 'ok: ' + txt.slice(0, 100);
        } catch(e) {
            return 'error: ' + e.message;
        }
    }""")
    print(f"  Cross-origin fetch from roblox.com: {result}", flush=True)

    # Test 4: Same-origin from roblox
    result = page.evaluate("""async () => {
        try {
            const resp = await fetch('/login');
            return 'ok: ' + resp.status;
        } catch(e) {
            return 'error: ' + e.message;
        }
    }""")
    print(f"  Same-origin fetch from roblox.com: {result}", flush=True)

    # Test 5: no-cors mode cross-origin
    result = page.evaluate("""async () => {
        try {
            const resp = await fetch('https://api.nopecha.com/v1/status', { mode: 'no-cors' });
            return 'ok: status=' + resp.status + ' type=' + resp.type;
        } catch(e) {
            return 'error: ' + e.message;
        }
    }""")
    print(f"  no-cors cross-origin fetch: {result}", flush=True)

proc.kill()
