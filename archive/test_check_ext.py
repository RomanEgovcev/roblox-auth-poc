import os, time
from playwright.sync_api import sync_playwright

ext_path = os.path.abspath(r'C:\Users\regov\Desktop\lua\chromium_automation')

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir='pw_profile2',
        headless=False,
        args=[
            "--no-proxy-server",
            f"--load-extension={ext_path}",
        ],
    )
    page = context.pages[0]
    
    # Open extensions page
    page.goto("chrome://extensions/", wait_until="domcontentloaded")
    time.sleep(3)
    
    # Take screenshot
    page.screenshot(path="ext_check.png")
    
    # Check for NopeCHA
    text = page.content()
    if "NopeCHA" in text:
        print("[+] NopeCHA extension FOUND in extensions list!")
    else:
        print("[-] NopeCHA NOT found in extensions list")
    
    # Also check by going to extension's popup directly
    # First, get extension ID
    import re
    ids = re.findall(r'chrome-extension://([a-z0-9]{32})/', text)
    if ids:
        print(f"[*] Extension IDs found: {set(ids)}")
        for eid in set(ids):
            try:
                pg2 = context.new_page()
                pg2.goto(f"chrome-extension://{eid}/assets/ip10n8.html", timeout=5000)
                time.sleep(1)
                print(f"[+] Popup loaded for {eid}")
                pg2.close()
            except Exception as ex:
                print(f"[-] Popup failed for {eid}: {ex}")
    
    print(f"\n[*] Screenshot saved to ext_check.png")
    print("[*] Browser open. Check it, then close.")
    time.sleep(60)
    context.close()
