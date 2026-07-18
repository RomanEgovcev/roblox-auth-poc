"""Use page.type() for real keyboard input."""
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
    
    all_requests = []
    page.on("request", lambda r: all_requests.append({"u": r.url[:150], "m": r.method, "t": time.time()}))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    page.click('#login-username')
    page.type('#login-username', USER, delay=50)
    
    page.click('#login-password')
    page.type('#login-password', PASS, delay=50)
    time.sleep(1)
    
    click_time = time.time()
    page.click('.login-button', timeout=5000)
    print("Clicked!", flush=True)
    
    time.sleep(10)
    
    auth_after = [r for r in all_requests if 'auth.roblox.com' in r['u'].split('?')[0] and r['t'] >= click_time]
    print(f"\nAuth requests after click ({len(auth_after)}):", flush=True)
    for r in auth_after:
        dt = round(r.get('t', 0) - click_time, 2)
        print(f"  [{dt:+.2f}s] {r['m']} {r['u'][:100]}", flush=True)
    
    all_after = [r for r in all_requests if r['m'] == 'POST' and r['t'] >= click_time]
    print(f"\nAll POSTs after click ({len(all_after)}):", flush=True)
    for r in all_after[:10]:
        dt = round(r.get('t', 0) - click_time, 2)
        print(f"  [{dt:+.2f}s] {r['u'][:100]}", flush=True)
    
    print(f"\nFinal URL: {page.url}", flush=True)
    
    time.sleep(2)
    browser.close()
