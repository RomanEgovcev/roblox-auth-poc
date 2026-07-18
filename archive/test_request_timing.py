"""Track request timestamps to distinguish preload vs click-triggered."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    events = []
    
    page.on("request", lambda r: events.append({
        "t": time.time(), "type": "req", 
        "url": r.url[:150], "method": r.method
    }))
    
    page.on("response", lambda r: events.append({
        "t": time.time(), "type": "resp",
        "url": r.url[:150], "status": r.status
    }))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    click_time = time.time()
    print(f"Click at t=0", flush=True)
    
    page.fill('#login-username', USER)
    page.fill('#login-password', PASS)
    time.sleep(1)
    
    page.click('.login-button', timeout=5000)
    
    time.sleep(10)
    end_time = time.time()
    
    # Filter auth-related events after click
    auth_events = [e for e in events if 'auth.roblox.com' in e['url'] and e['t'] >= click_time - 0.5]
    
    print(f"\nAuth events after/few seconds before click:", flush=True)
    for e in sorted(auth_events, key=lambda x: x['t']):
        dt = round(e['t'] - click_time, 2)
        if e['type'] == 'req':
            print(f"  [{dt:+.2f}s] REQ  {e['method']} {e['url'][:100]}", flush=True)
        else:
            print(f"  [{dt:+.2f}s] RESP {e['status']} {e['url'][:100]}", flush=True)
    
    # Also look at passkey and challenge events
    passkey_events = [e for e in events if 'passkey' in e['url'].lower() and e['t'] >= click_time - 0.5]
    if passkey_events:
        print(f"\nPasskey events:", flush=True)
        for e in sorted(passkey_events, key=lambda x: x['t']):
            dt = round(e['t'] - click_time, 2)
            if e['type'] == 'req':
                print(f"  [{dt:+.2f}s] REQ  {e['url'][:100]}", flush=True)
            else:
                print(f"  [{dt:+.2f}s] RESP {e['status']} {e['url'][:100]}", flush=True)
    
    time.sleep(2)
    browser.close()
