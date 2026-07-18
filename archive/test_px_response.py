"""Monitor PX collector response without intercepting."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    px_responses = []
    page.on("response", lambda r: px_responses.append({"url": r.url[:150], "status": r.status}) if 'collector' in r.url or 'px-cdn' in r.url or 'pxchk' in r.url else None)
    
    # Track body separately
    actual_bodies = []
    def track_body(r):
        if 'collector' in r.url or 'px-cdn' in r.url:
            r.body().then(lambda b: actual_bodies.append({"url": r.url[:100], "body": b[:1000]}))
    page.on("response", track_body)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    page.click("#login-button", timeout=5000)
    print("[*] Clicked", flush=True)
    
    time.sleep(5)
    
    for r in px_responses:
        print(f"  PX: {r}", flush=True)
    
    print(f"\nBodies ({len(actual_bodies)}):", flush=True)
    for b in actual_bodies:
        print(f"  {b['url']}: {b['body'][:500]}", flush=True)
    
    input("Enter...")
    browser.close()
