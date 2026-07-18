"""Exact same approach as working pure test: launch + new_context + wait_for_response."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    # Track
    auth_response = [None]
    def on_resp(r):
        if 'auth.roblox.com' in r.url:
            auth_response[0] = r
    page.on('response', on_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)  # generous wait for page init
    
    # Fill
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    time.sleep(1)
    
    # Check button exists
    btn_ok = page.evaluate("() => !!document.querySelector('#login-button')")
    print(f"[*] Login button exists: {btn_ok}", flush=True)
    btn_text = page.evaluate("() => document.querySelector('#login-button')?.textContent")
    print(f"[*] Button text: {btn_text}", flush=True)
    
    # Click via evaluate
    print("[*] Clicking btn.click()...", flush=True)
    page.evaluate("document.querySelector('#login-button')?.click()")
    print("[*] Clicked", flush=True)
    
    # Wait for auth response
    t0 = time.time()
    auth = None
    while time.time() - t0 < 30:
        if auth_response[0] is not None:
            auth = auth_response[0]
            break
        time.sleep(0.5)
    
    if auth:
        print(f"[+] Auth response: {auth.status} {auth.url[:100]}", flush=True)
        body = auth.body()
        print(f"[+] Body: {body[:500]}", flush=True)
        
        # Check PX
        if b'<html>' in body[:100] or b'px-captcha' in body:
            print("[*] Response is HTML (PX challenge)", flush=True)
        elif body.startswith(b'{"'):
            print(f"[*] Response is JSON: {body[:200]}", flush=True)
        
        # Now wait for enforcement frame
        print("[*] Waiting for enforcement...", flush=True)
        for i in range(90):
            enf = [f for f in page.frames if 'enforcement' in f.url]
            game = [f for f in page.frames if 'game-core' in f.url]
            if i % 10 == 0:
                print(f"[{i}s] frames:{len(page.frames)} enf:{bool(enf)} game:{bool(game)}", flush=True)
            if enf:
                print(f"[+] Enforcement at {i}s", flush=True)
                break
            time.sleep(1)
        else:
            print("[-] No enforcement", flush=True)
    else:
        print(f"[-] No auth response in 30s", flush=True)
        print(f"URL: {page.url[:200]}", flush=True)
        page.screenshot(path="noauth.png")
        # Check what happened - any network requests?
        page.evaluate("() => console.log('URL after:', window.location.href)")
        time.sleep(2)
        print(f"URL after check: {page.url[:200]}", flush=True)
    
    input("[*] Press Enter...")
    browser.close()
