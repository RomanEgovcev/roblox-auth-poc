import os, sys, time, subprocess
from playwright.sync_api import sync_playwright

ext_path = os.path.abspath(r'C:\Users\regov\Desktop\lua\chromium_automation')
profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')
pac_url = "file:///C:/Users/regov/Desktop/lua/proxy.pac"

with sync_playwright() as p:
    chrome_path = p.chromium.executable_path
    print(f"[*] Chromium: {chrome_path}", flush=True)

    proc = subprocess.Popen(
        [chrome_path,
         f"--user-data-dir={profile}",
         f"--load-extension={ext_path}",
         "--no-first-run",
         f"--proxy-pac-url={pac_url}",
         "chrome://extensions/"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("[*] Chromium opened. Verify NopeCHA is in the extensions list.", flush=True)
    print("[*] Then close the browser window.", flush=True)
    proc.wait()
    print("[*] Done. Extension should be installed.", flush=True)
