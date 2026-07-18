"""Full network trace of page.click - capture EVERYTHING."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    requests_log = []
    page.on("request", lambda r: requests_log.append({
        "url": r.url[:200],
        "method": r.method,
        "type": r.resource_type,
        "headers": dict(r.headers),
        "post_data": r.post_data[:500] if r.post_data else None
    }))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    time.sleep(1)
    
    # Clear log
    requests_log.clear()
    
    print("[*] Clicking login...", flush=True)
    page.click("#login-button", timeout=5000)
    print("[*] Clicked", flush=True)
    
    time.sleep(10)
    
    # Print all requests after click
    print(f"\nRequests after click ({len(requests_log)}):", flush=True)
    for r in requests_log:
        url = r['url']
        if any(kw in url for kw in ['auth', 'login', 'hba', 'nonce', 'metric', 'captcha', 'challenge', 'px', 'arkose']):
            print(f"  [{r['method']}] {url[:120]}", flush=True)
            if r.get('post_data'):
                print(f"    POST: {r['post_data'][:200]}", flush=True)
    
    # Check for any auth requests
    auth = [r for r in requests_log if 'auth.roblox' in r['url']]
    if auth:
        print(f"\nAuth requests found: {len(auth)}", flush=True)
        for a in auth:
            print(f"  {a['method']} {a['url']}", flush=True)
    else:
        print(f"\nNO auth requests. All requests:", flush=True)
        for r in requests_log:
            print(f"  [{r['method']}] {r['url'][:120]}", flush=True)
    
    print(f"\nCurrent URL: {page.url[:200]}", flush=True)
    
    input("Enter...")
    browser.close()
