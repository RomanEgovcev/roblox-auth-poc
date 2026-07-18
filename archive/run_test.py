import os, sys, time, json, subprocess
from playwright.sync_api import sync_playwright

ext_path = os.path.abspath(r'C:\Users\regov\Desktop\lua\chromium_automation')
profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')
username = sys.argv[1] if len(sys.argv) > 1 else "CheatingHitmanner"
password = sys.argv[2] if len(sys.argv) > 2 else ""

# Check if extension is already installed in profile
ext_installed = False
prefs_path = os.path.join(profile, "Default", "Preferences")
if os.path.exists(prefs_path):
    try:
        with open(prefs_path, "r", encoding="utf-8") as f:
            prefs = json.load(f)
        settings = prefs.get("extensions", {}).get("settings", {})
        for eid, data in settings.items():
            if "unpacked" in str(data.get("path", "")).lower() or "nopecha" in str(data.get("name", "")).lower():
                ext_installed = True
                break
    except:
        pass

if not ext_installed:
    print("[*] Installing extension in profile...", flush=True)
    with sync_playwright() as p:
        chrome_path = p.chromium.executable_path
    proc = subprocess.Popen(
        [chrome_path,
         f"--user-data-dir={profile}",
         f"--load-extension={ext_path}",
         "--no-first-run",
         "--no-proxy-server",
         "chrome://extensions/"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("[*] Chromium opened. Check NopeCHA, then close.", flush=True)
    proc.wait()
    print("[*] Installing done.\n", flush=True)

# Now run the login test
print("[*] Launching login test...", flush=True)
with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=profile,
        headless=False,
        args=["--proxy-pac-url=file:///C:/Users/regov/Desktop/lua/proxy.pac"],
    )
    page = context.pages[0]
    page.set_default_timeout(15000)

    # Verify extension
    page.goto("chrome://extensions/", wait_until="domcontentloaded")
    time.sleep(1)
    if 'NopeCHA' in page.content():
        print("[+] NopeCHA loaded!", flush=True)
    else:
        print("[-] NopeCHA NOT loaded!", flush=True)

    # Login
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    page.wait_for_selector("#login-username", timeout=30000)
    page.fill("#login-username", username)
    page.fill("#login-password", password)
    time.sleep(1)

    for sel in ["button[data-testid='login-button']", "#login-button"]:
        btn = page.query_selector(sel)
        if btn:
            btn.click(force=True)
            print(f"[*] Clicked: {sel}", flush=True)
            break

    print("[*] Observing. Close browser when done.\n", flush=True)
    for i in range(120):
        time.sleep(1)
        url = page.url
        info = f"  [{i+1}s] {url[:70]}"
        try:
            dom = page.evaluate("""() => {
                const arkose = document.querySelector('#arkose-0, .arkose-wrapper');
                const captcha = document.querySelector('iframe[src*="arkoselabs"]');
                return {arkose: !!arkose, captcha: !!captcha};
            }""")
            if dom['arkose'] or dom['captcha']:
                info += " [CAPTCHA]"
        except:
            pass
        print(info, flush=True)
        if "home" in url:
            print("\n[+] LOGGED IN!", flush=True)
            cookies = context.cookies()
            for c in cookies:
                if c['name'] == '.ROBLOSECURITY':
                    print(f"[+] COOKIE: {c['value'][:50]}...")
            break
    context.close()
