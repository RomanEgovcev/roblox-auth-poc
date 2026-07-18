"""Block PX entirely and check auth flow."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    auth_responses = []
    def track(r):
        if 'auth.roblox' in r.url:
            auth_responses.append({"url": r.url[:150], "status": r.status})
    page.on("response", track)
    
    def block_px(route):
        url = route.request.url
        if 'collector' in url and 'px-cloud' in url:
            route.fulfill(status=200, content_type='application/json', body='{"status":"ok"}')
        elif 'main.min.js' in url and 'px-cloud' in url:
            print(f"[*] Blocking PX script: {url[:80]}", flush=True)
            route.fulfill(status=200, content_type='application/javascript', body='')
        elif 'px-cdn' in url or 'px-cloud' in url:
            route.abort()
        else:
            route.continue_()
    
    page.route("**/*", block_px)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    page.click("#login-button", timeout=5000)
    print("[*] Clicked", flush=True)
    
    for i in range(30):
        auth = [r for r in auth_responses if 'auth.roblox' in r['url']]
        if auth:
            print(f"[+] Auth at {i}s: {auth[-1]}", flush=True)
            break
        time.sleep(0.5)
    else:
        print(f"[-] No auth in 15s. Total responses: {len(auth_responses)}", flush=True)
        for r in auth_responses[:20]:
            print(f"  {r['url']} -> {r['status']}", flush=True)
    
    page.screenshot(path="block_px.png")
    input("Enter...")
    browser.close()
