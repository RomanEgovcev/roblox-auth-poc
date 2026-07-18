"""Capture console errors after login click."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Capture console messages
    console_msgs = []
    page.on("console", lambda msg: console_msgs.append({"type": msg.type, "text": msg.text[:200]}))
    
    # Capture page errors
    page_errors = []
    page.on("pageerror", lambda err: page_errors.append(str(err)[:300]))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    page.fill('#login-username', USER)
    page.fill('#login-password', PASS)
    time.sleep(1)
    
    page.click('.login-button', timeout=5000)
    print("Clicked!", flush=True)
    
    time.sleep(10)
    
    # Print errors
    errors = [m for m in console_msgs if m['type'] in ['error', 'warning']]
    print(f"\nConsole errors/warnings ({len(errors)}):", flush=True)
    for e in errors[:15]:
        print(f"  [{e['type']}] {e['text']}", flush=True)
    
    print(f"\nPage errors ({len(page_errors)}):", flush=True)
    for e in page_errors[:10]:
        print(f"  {e}", flush=True)
    
    # Find the error div HTML
    error_div = page.evaluate("""() => {
        const alert = document.querySelector('[class*="alert-info"]');
        if (alert) return {html: alert.outerHTML, parent: alert.parentElement ? alert.parentElement.className : 'none'};
        return null;
    }""")
    print(f"\nError div: {json.dumps(error_div, indent=2)}", flush=True)
    
    # Check if it comes from noscript
    noscript = page.evaluate("""() => {
        const ns = document.querySelector('noscript');
        if (ns) return {html: ns.innerHTML.substring(0, 300)};
        return null;
    }""")
    print(f"\nNoscript: {json.dumps(noscript, indent=2)}", flush=True)
    
    time.sleep(2)
    browser.close()
