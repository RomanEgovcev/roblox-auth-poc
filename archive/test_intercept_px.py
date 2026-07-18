"""Intercept PX collector to make login work."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    # Intercept PX collector - return safe response
    def intercept_px(route):
        if 'collector' in route.request.url:
            # Return empty success response to bypass PX risk eval
            print(f"[*] Intercepting PX collector: {route.request.url[:80]}", flush=True)
            route.fulfill(
                status=200,
                content_type='text/plain',
                body='[]'  # Empty response - no risk assessment needed
            )
        else:
            route.continue_()
    
    page.route("**/collector**", intercept_px)
    page.route("**px-cloud.net/**", intercept_px)
    
    auth_responses = []
    page.on("response", lambda r: auth_responses.append({"url": r.url[:150], "status": r.status}) if 'auth.roblox' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    page.click("#login-button", timeout=5000)
    print("[*] Clicked", flush=True)
    
    for i in range(30):
        if any('auth.roblox' in r['url'] for r in auth_responses):
            print(f"[+] Auth at {i}s: {auth_responses[-1]}", flush=True)
            break
        time.sleep(0.5)
    else:
        print(f"[-] No auth in 15s. Auth: {auth_responses}", flush=True)
    
    # Wait for enforcement frames
    print("[*] Waiting for enforcement...", flush=True)
    for i in range(60):
        game = [f for f in page.frames if 'game-core' in f.url]
        enf = [f for f in page.frames if ('enforcement' in f.url and 'roblox' in f.url)]
        if i % 10 == 0:
            print(f"[{i}s] frames:{len(page.frames)} game:{bool(game)} enf:{bool(enf)}", flush=True)
        if game:
            print(f"[++] GAME-CORE at {i}s: {game[0].url[:150]}", flush=True)
            break
        time.sleep(1)
    else:
        print("[-] No frames", flush=True)
        page.screenshot(path="intercept_fail.png")
    
    input("Enter...")
    browser.close()
