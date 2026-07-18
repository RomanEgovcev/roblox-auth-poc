import os, time, re
from playwright.sync_api import sync_playwright

ext_path = os.path.abspath(r'C:\Users\regov\Desktop\lua\chromium_automation')
profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_diag')

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=profile,
        headless=False,
        args=[
            "--no-proxy-server",
            f"--load-extension={ext_path}",
        ],
    )
    page = context.pages[0]

    # Capture console errors
    errors = []
    page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}"))

    page.goto("chrome://extensions/", wait_until="domcontentloaded")
    time.sleep(3)

    # Enable developer mode (need to click toggle - might fail)
    try:
        dev_toggle = page.query_selector("#devMode")
        if dev_toggle:
            dev_toggle.click()
            time.sleep(1)
    except:
        pass

    html = page.content()
    page.screenshot(path="ext_diag.png")

    # Search for any extension
    ext_ids = re.findall(r'chrome-extension://([a-z0-9]{32})', html)
    nopecha_in_html = 'NopeCHA' in html or 'nopecha' in html.lower() or 'funcaptcha' in html
    any_ext = 'extensions-list' in html and ('extension-list-item' in html or 'extensions-item' in html)

    print(f"[*] NopeCHA in HTML: {nopecha_in_html}", flush=True)
    print(f"[*] Any extensions listed: {any_ext}", flush=True)
    print(f"[*] Extension IDs found: {ext_ids}", flush=True)
    print(f"[*] Console errors ({len(errors)}):", flush=True)
    for e in errors[:10]:
        print(f"  {e}", flush=True)
    
    # Check also service workers
    time.sleep(2)
    sw_page = context.new_page()
    sw_page.goto("chrome://serviceworker-internals/", wait_until="domcontentloaded")
    time.sleep(2)
    sw_html = sw_page.content()
    if 'nopecha' in sw_html.lower():
        print("[+] NopeCHA service worker found!", flush=True)
    else:
        print("[-] No NopeCHA service worker", flush=True)
    sw_page.close()

    print(f"\n[*] Screenshot: ext_diag.png", flush=True)
    print("[*] Browser open. Check extensions page manually, then close.", flush=True)
    time.sleep(120)
    context.close()
