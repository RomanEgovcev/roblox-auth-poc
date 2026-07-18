import os, sys, time
from playwright.sync_api import sync_playwright

ext_path = os.path.abspath(r'C:\Users\regov\Desktop\lua\chromium_automation')
print(f"Extension path: {ext_path}")
print(f"Exists: {os.path.isdir(ext_path)}")

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile'),
        headless=False,
        args=[
            f"--disable-extensions-except={ext_path}",
            f"--load-extension={ext_path}",
        ],
    )
    page = context.pages[0]
    page.goto("chrome://extensions/")
    print("Browser open. Check chrome://extensions/ for NopeCHA")
    time.sleep(30)
    context.close()
    print("Done")
