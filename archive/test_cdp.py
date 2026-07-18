"""Connect to running Chrome via CDP for real browser profile."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

# First launch regular Chrome with remote debugging
os.system("start chrome.exe --remote-debugging-port=9222 --user-data-dir=%TEMP%\\chrome_test_profile")
time.sleep(3)

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    
    # Check existing pages
    contexts = browser.contexts
    pages = browser.pages
    print(f"Contexts: {len(contexts)}, Pages: {len(pages)}", flush=True)
    
    if pages:
        page = pages[0]
        print(f"Current URL: {page.url}", flush=True)
    else:
        page = browser.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        resp = response_info.value
        print(f"[+] Auth: {resp.status}", flush=True)
        
        headers = dict(resp.headers)
        chal_type = headers.get('rblx-challenge-type', 'N/A')
        chal_id = headers.get('rblx-challenge-id', 'N/A')
        chal_meta_b64 = headers.get('rblx-challenge-metadata', '')
        
        print(f"[+] Type: {chal_type}", flush=True)
        if chal_id != 'N/A':
            print(f"[+] ID: {chal_id[:30]}...", flush=True)
        
        if chal_meta_b64:
            pad = len(chal_meta_b64) % 4
            if pad:
                chal_meta_b64 += '=' * (4 - pad)
            meta = json.loads(base64.b64decode(chal_meta_b64))
            sp = meta.get('sharedParameters', {})
            print(f"[+] eligibleMethods: {sp.get('eligibleMethods', 'N/A')}", flush=True)
            print(f"[+] renderNative: {sp.get('renderNativeChallenge', 'N/A')}", flush=True)
    except Exception as e:
        print(f"[-] No auth: {e}", flush=True)
    
    time.sleep(5)
    
    frames = page.frames
    arkose = [f for f in frames if 'arkose' in f.url]
    enforcement = [f for f in frames if 'enforcement' in f.url]
    print(f"Frames: {len(frames)}, arkose: {len(arkose)}, enforcement: {len(enforcement)}", flush=True)
    
    page.screenshot(path="cdp_test.png")
    print("[*] Done. Close Chrome manually.", flush=True)
    time.sleep(60)
    browser.close()
