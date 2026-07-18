"""Pure test: login without ANY extension, fresh Playwright browser."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(3)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    # Use regular Chrome, no extension, no profile
    browser = p.chromium.launch(headless=False, args=[
        "--disable-blink-features=AutomationControlled",
        "--no-first-run"
    ])
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(5)
    
    # Log all requests
    requests_log = []
    page.on("request", lambda r: requests_log.append({"url": r.url[:150], "method": r.method, "post": (r.post_data or '')[:200]}))
    page.on("response", lambda r: requests_log.append({"url": r.url[:150], "status": r.status}))
    
    # Fill using Playwright's native fill
    print("[*] Filling form...", flush=True)
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    page.click("#login-button")
    
    time.sleep(5)
    
    # Log requests
    print(f"\nURL: {page.url[:200]}", flush=True)
    
    # Check for auth requests
    auth_reqs = [r for r in requests_log if 'auth.roblox' in r['url']]
    print(f"Auth requests: {auth_reqs}", flush=True)
    
    login_reqs = [r for r in requests_log if 'login' in r['url'].lower()]
    print(f"Login requests: {len(login_reqs)}", flush=True)
    for r in login_reqs[:10]:
        print(f"  {r}", flush=True)
    
    if not auth_reqs:
        print("[!] NO AUTH REQUEST - form submit failed!", flush=True)
        # Try JS click fallback
        print("[*] Trying JS click...", flush=True)
        page.evaluate("document.querySelector('#login-button')?.click()")
        time.sleep(3)
        auth_reqs = [r for r in requests_log if 'auth.roblox' in r['url']]
        print(f"After JS click: {auth_reqs}", flush=True)
    
    # Also check if the page has any error
    error = page.evaluate("() => document.querySelector('.error, [class*=alert], [class*=message]')?.textContent || 'none'")
    print(f"Error message: {error}", flush=True)
    
    browser.close()
