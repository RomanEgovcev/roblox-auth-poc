"""Use page.fill() for proper React form interaction."""
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
    
    responses = []
    requests = []
    page.on("response", lambda r: responses.append({"url": r.url[:200], "status": r.status}))
    page.on("request", lambda r: requests.append({"url": r.url[:200], "method": r.method}))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Use Playwright's fill (handles React properly)
    page.fill('#login-username', USER)
    page.fill('#login-password', PASS)
    time.sleep(1)
    
    # Verify values
    vals = page.evaluate("""() => ({
        username: document.getElementById('login-username')?.value,
        password: document.getElementById('login-password')?.value,
    })""")
    print(f"Filled values: {vals}", flush=True)
    
    page.click('.login-button', timeout=5000)
    print("Clicked!", flush=True)
    
    time.sleep(12)
    
    auth_posts = [r for r in requests if 'auth.roblox.com' in r['url'] and r['method'] == 'POST']
    print(f"\nAuth POSTs ({len(auth_posts)}):", flush=True)
    for r in auth_posts:
        print(f"  {r['url'][:120]}", flush=True)
    
    # Also get full auth responses
    auth_resps = [r for r in responses if 'auth.roblox.com' in r['url'] and 'login' in r['url'].lower()]
    print(f"\nAuth login responses ({len(auth_resps)}):", flush=True)
    for r in auth_resps:
        print(f"  [{r['status']}] {r['url'][:120]}", flush=True)
    
    time.sleep(2)
    browser.close()
