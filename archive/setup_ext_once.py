import os, time
from playwright.sync_api import sync_playwright

ext_path = os.path.abspath(r'C:\Users\regov\Desktop\lua\chromium_automation')

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir='pw_profile',
        headless=False,
    )
    page = context.pages[0]

    # Open extensions page
    page.goto("chrome://extensions/", wait_until="domcontentloaded")
    time.sleep(2)

    # Enable developer mode by clicking the toggle
    try:
        # Try to find the dev mode toggle
        toggle = page.query_selector("#devMode")
        if toggle:
            toggle.click()
            time.sleep(1)
            print("[*] Developer mode enabled", flush=True)
    except:
        pass

    # Click "Load unpacked" button
    try:
        load_btn = page.query_selector("button[aria-pressed='false'] cr-button, cr-button:has-text('Load unpacked'), .load-unpacked")
        if not load_btn:
            load_btn = page.query_selector("button:has-text('Load unpacked'), cr-button:has-text('Load unpacked')")
        if load_btn:
            load_btn.click()
            time.sleep(1)
            # Navigate in the file dialog is not possible via Playwright
            # Instead, use keyboard shortcut
        else:
            print("[*] Load unpacked button not found, trying to paste path", flush=True)
    except Exception as e:
        print(f"[*] Click error: {e}", flush=True)

    # On Windows, the file dialog is a system dialog - can't automate via Playwright.
    # Instead, we'll navigate to the extensions page and let the user click "Load unpacked" manually.
    
    print("\n" + "="*60, flush=True)
    print("MANUAL STEP: Click 'Load unpacked' and select:", flush=True)
    print(f"  {ext_path}", flush=True)
    print("="*60, flush=True)
    
    time.sleep(120)
    context.close()
