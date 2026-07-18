"""Login test with no proxy - fresh IP, no rate limit."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=["--no-proxy-server"]  # bypass system proxy
    )
    context = browser.new_context()
    page = context.new_page()
    
    auth_reqs = []
    page.on("response", lambda r: auth_reqs.append({"url": r.url[:200], "status": r.status}) if 'auth.roblox' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Track console for CORS errors
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text[:200]) if msg.type == 'error' else None)
    
    print("[*] Trying page.click (real mouse)...", flush=True)
    page.click("#login-button", timeout=5000)
    print("[*] Clicked", flush=True)
    
    time.sleep(5)
    
    print(f"Auth: {[(r['url'][:60], r['status']) for r in auth_reqs]}", flush=True)
    cors_errors = [e for e in console_errors if 'CORS' in e or 'auth.roblox' in e]
    print(f"CORS errors: {cors_errors}", flush=True)
    print(f"URL: {page.url[:150]}", flush=True)
    
    if auth_reqs:
        print("[+] LOGIN WORKS WITHOUT PROXY!", flush=True)
    else:
        print("[-] Still blocked", flush=True)
    
    input("Enter...")
    browser.close()
