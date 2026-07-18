"""Read login response body with challenge details."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"
CAPTURED = {}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Capture login response
    page.on("response", lambda r: CAPTURED.update({
        "status": r.status,
        "headers": dict(r.headers),
        "body": r.text()[:500]
    }) if '/v2/login' in r.url and 'urlLocale' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    page.fill('#login-username', USER)
    page.fill('#login-password', PASS)
    time.sleep(1)
    
    page.click('.login-button', timeout=5000)
    print("Clicked!", flush=True)
    time.sleep(10)
    
    if CAPTURED:
        print(f"\nLogin response:", flush=True)
        print(f"  Status: {CAPTURED['status']}", flush=True)
        h = CAPTURED['headers']
        
        chall_id = h.get('rblx-challenge-id', '')
        chall_type = h.get('rblx-challenge-type', '')
        chall_meta_b64 = h.get('rblx-challenge-metadata', '')
        csrf = h.get('x-csrf-token', '')
        
        print(f"  CSRF: {csrf}", flush=True)
        if chall_id:
            print(f"  Challenge: {chall_id} ({chall_type})", flush=True)
            if chall_meta_b64:
                try:
                    meta = json.loads(base64.b64decode(chall_meta_b64 + '==').decode())
                    print(f"  Metadata: {json.dumps(meta, indent=2)}", flush=True)
                except:
                    print(f"  Metadata: {chall_meta_b64[:100]}...", flush=True)
        
        body = CAPTURED.get('body', '')
        if body:
            print(f"  Body: {body[:300]}", flush=True)
    else:
        print("\nNo login response captured!", flush=True)
        # Check if click actually triggered anything
        print("Checking if button click worked...", flush=True)
    
    time.sleep(2)
    browser.close()
