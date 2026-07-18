import os, sys, time
from playwright.sync_api import sync_playwright

ext_path = os.path.abspath(r'C:\Users\regov\Desktop\lua\chromium_automation')
username = sys.argv[1] if len(sys.argv) > 1 else "CheatingHitmanner"
password = sys.argv[2] if len(sys.argv) > 2 else ""

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir='pw_profile',
        headless=False,
        channel='chrome',
        args=[
            "--no-proxy-server",
            f"--load-extension={ext_path}",
        ],
    )
    page = context.pages[0]
    page.set_default_timeout(15000)
    page.goto("chrome://extensions/", wait_until="domcontentloaded")
    time.sleep(2)
    html = page.content()
    if 'NopeCHA' in html:
        print("[+] NopeCHA extension FOUND!", flush=True)
    else:
        print("[-] NopeCHA NOT found in extensions", flush=True)
    print("[*] Browser open. Close manually.", flush=True)
    time.sleep(120)
    context.close()
