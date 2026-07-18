import os, sys, time, json
from playwright.sync_api import sync_playwright

username = sys.argv[1] if len(sys.argv) > 1 else "CheatingHitmanner"
password = sys.argv[2] if len(sys.argv) > 2 else ""
pac_url = "file:///C:/Users/regov/Desktop/lua/proxy.pac"
profile = os.path.abspath('pw_profile')
prefs_path = os.path.join(profile, "Default", "Preferences")

# Check extension in Preferences file
if os.path.exists(prefs_path):
    with open(prefs_path, "r", encoding="utf-8") as f:
        prefs = json.load(f)
    settings = prefs.get("extensions", {}).get("settings", {})
    print(f"[*] Extensions in Preferences: {len(settings)}", flush=True)
    for eid, data in settings.items():
        path = data.get("path", "")
        print(f"  {eid}: path={path[-50:]}", flush=True)
else:
    print(f"[-] Preferences file not found at {prefs_path}", flush=True)

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=profile,
        headless=False,
        args=["--disable-automation", f"--proxy-pac-url={pac_url}"],
    )
    page = context.pages[0]
    page.set_default_timeout(15000)

    # Check extensions page
    page.goto("chrome://extensions/", wait_until="domcontentloaded")
    time.sleep(3)
    page.screenshot(path="ext_page.png")
    
    html = page.content()
    if 'NopeCHA' in html:
        print("[+] NopeCHA loaded in browser!", flush=True)
    else:
        print("[-] NopeCHA NOT loaded in browser", flush=True)
        # Print what IS in extensions
        import re
        ext_names = re.findall(r'<title>([^<]+)</title>', html)
        print(f"  Page title: {ext_names}", flush=True)

    # Check also via extensions service worker API
    try:
        result = page.evaluate("""() => {
            return new Promise(resolve => {
                if (typeof chrome === 'undefined' || !chrome.runtime) {
                    resolve('no chrome.runtime');
                    return;
                }
                chrome.management.getAll(exts => {
                    resolve(exts.map(e => e.name + ' ' + e.id).join(', '));
                });
            });
        }""")
        print(f"[*] chrome.management: {result}", flush=True)
    except Exception as e:
        print(f"[*] management error: {e}", flush=True)
    
    if 'NopeCHA' not in html:
        time.sleep(30)
        context.close()
        sys.exit(1)

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
