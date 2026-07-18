"""Read PX collector response synchronously."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    # Use route to capture the response body
    px_body = [None]
    def handle_px(route):
        if 'collector' in route.request.url:
            resp = route.request.response()
            if resp:
                body = resp.body()
                px_body[0] = body[:2000]
                print(f"[*] Intercepted PX response: {body[:500]}", flush=True)
                route.continue_()
            else:
                route.continue_()
        else:
            route.continue_()
    
    page.route("**px-cloud.net/**", handle_px)
    page.route("**pxchk.net/**", handle_px)
    page.route("**px-cdn.net/**", handle_px)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking...", flush=True)
    page.click("#login-button", timeout=5000)
    time.sleep(5)
    
    if px_body[0]:
        print(f"\nPX collector body: {px_body[0][:1000]}", flush=True)
    else:
        print("No PX body captured", flush=True)
    
    input("Enter...")
    browser.close()
