"""Debug - check if click triggers anything at all."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    all_requests = []
    page.on("request", lambda r: all_requests.append({"url": r.url[:150], "method": r.method}))
    page.on("console", lambda msg: print(f"  [{msg.type}] {msg.text[:200]}", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Clear the request log to only track after click
    all_requests.clear()
    
    print("[*] Clicking login button...", flush=True)
    page.click("#login-button", timeout=5000)
    print("[*] Click done", flush=True)
    
    time.sleep(5)
    
    print(f"\n=== Requests after click ({len(all_requests)}) ===", flush=True)
    for r in all_requests:
        print(f"  {r['method']} {r['url']}", flush=True)
    
    print(f"\nURL: {page.url[:150]}", flush=True)
    
    input("Enter...")
    browser.close()
