"""Pure test - launch() not launch_persistent, click and wait for enforcement."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    # Track all requests/responses
    auth_resp = []
    all_reqs = []
    page.on("response", lambda r: auth_resp.append(r) if 'auth.roblox' in r.url and r.status == 403 else None)
    page.on("request", lambda r: all_reqs.append(r.url) if 'auth.roblox' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Click using various methods
    print("[*] page.click...", flush=True)
    page.click("#login-button", timeout=5000)
    print("[*] Clicked", flush=True)
    
    # Wait for auth response
    for i in range(20):
        if auth_resp:
            print(f"[+] Auth 403 at {i}s: {auth_resp[-1].url[:80]}", flush=True)
            break
        time.sleep(0.5)
    else:
        print(f"[-] No 403 response. All auth reqs: {[r[:80] for r in all_reqs]}", flush=True)
    
    # Wait for enforcement
    print("[*] Waiting for enforcement frames...", flush=True)
    for i in range(60):
        frames_info = [(f.url[:120], len(f.frames)) for f in page.frames]
        enf = [f for f in page.frames if 'enforcement' in f.url or 'arkoselabs' in f.url]
        game = [f for f in page.frames if 'game-core' in f.url]
        if i % 10 == 0:
            print(f"[{i}s] enf:{bool(enf)} game:{bool(game)} frames:{len(page.frames)}", flush=True)
        if enf:
            print(f"[+] Enforcement: {enf[0].url[:120]}", flush=True)
        if game:
            print(f"[+] Game-core: {game[0].url[:120]}", flush=True)
        if game:
            print("[++] GOT GAME-CORE!", flush=True)
            break
        time.sleep(1)
    else:
        page.screenshot(path="pure_fail.png")
        print(f"[-] No game-core. Frames: {[f.url[:100] for f in page.frames]}", flush=True)
    
    input("Enter...")
    browser.close()
