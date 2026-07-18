"""Test if cryptoUtil.generateSecureAuthIntentV2 works and if patching fixes onFormSubmit."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("pageerror", lambda err: print(f"[PAGE_ERROR] {err}", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    # Test calling generateSecureAuthIntentV2
    result = page.evaluate("""async () => {
        const cu = window.CoreRobloxUtilities.cryptoUtil;
        if (!cu || typeof cu.generateSecureAuthIntentV2 !== 'function') {
            return 'not found: ' + typeof cu.generateSecureAuthIntentV2;
        }
        try {
            const intent = await cu.generateSecureAuthIntentV2();
            return 'success: ' + JSON.stringify(intent).substring(0, 100);
        } catch(e) {
            return 'error: ' + e.message + ' | ' + (e.stack || '').substring(0, 200);
        }
    }""")
    print(f"generateSecureAuthIntentV2: {result}", flush=True)
    
    # Try to find the servies reference f to see what cryptoUtil it uses
    result2 = page.evaluate("""() => {
        const cu = window.CoreRobloxUtilities;
        if (!cu) return 'no CoreRobloxUtilities';
        const keys = Object.getOwnPropertyNames(cu);
        return 'CoreRobloxUtilities keys: ' + keys.join(', ');
    }""")
    print(result2, flush=True)
    
    time.sleep(3)
    browser.close()
