import os, time
from playwright.sync_api import sync_playwright

test_ext = os.path.abspath(r'C:\Users\regov\Desktop\lua\test_ext')
with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir='pw_test',
        headless=False,
        args=["--no-proxy-server", f"--load-extension={test_ext}"],
    )
    page = context.pages[0]
    page.goto("chrome://extensions/", wait_until="domcontentloaded")
    time.sleep(2)
    html = page.content()
    if 'Test' in html:
        print("[+] TEST EXTENSION LOADED!")
    else:
        print("[-] Test extension NOT loaded")
    page.screenshot(path="test_ext.png")
    print("[*] Screenshot saved. Close browser.")
    time.sleep(30)
    context.close()
