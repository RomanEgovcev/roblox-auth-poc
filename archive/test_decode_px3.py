"""Decode _px3 cookie value."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

# Fast test: just load page, check cookies after login click
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    page.click("#login-button", timeout=5000)
    time.sleep(5)
    
    # Get cookies
    cookies = page.context.cookies()
    for c in cookies:
        if '_px' in c['name']:
            val = c['value']
            print(f"{c['name']}: {val[:80]}... (len={len(val)})", flush=True)
            
            # Try to decode _px3 (usually base64 after first 32 chars)
            if c['name'] == '_px3' and len(val) > 32:
                # First 32 chars might be hex prefix
                raw_part = val[32:]  # Skip potential hex prefix
                try:
                    decoded = base64.b64decode(raw_part)
                    print(f"  Decoded ({len(decoded)} bytes): {decoded[:100]}...", flush=True)
                    print(f"  Hex: {decoded[:50].hex()}", flush=True)
                except:
                    try:
                        decoded = base64.b64decode(val)
                        print(f"  Full decode: {decoded[:100]}...", flush=True)
                    except:
                        print(f"  Not base64: {raw_part[:50]}", flush=True)
            
            if c['name'] == '_pxvid':
                print(f"  visitor ID: {val}", flush=True)
    
    time.sleep(5)
    browser.close()
