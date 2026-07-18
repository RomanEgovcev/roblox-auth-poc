"""Force collector response to challenge instead of allow."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")
patched = patched.replace("new EvalError", "new Error")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        elif 'collector-pxbf8propw' in url and 'collector' in url:
            # Return forged challenge response
            forged = json.dumps({"do":"c","ob":""})
            print(f"[Collector] Forged: do=c (was null)", flush=True)
            route.fulfill(status=200, body=forged, content_type='application/json')
        else:
            route.continue_()
    
    page.route("**/*", intercept)
    
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
    except Exception as e:
        print(f"[-] No auth: {e}", flush=True)
    
    time.sleep(5)
    
    frames = page.frames
    game_core = sum(1 for f in frames if 'game-core' in f.url or 'arkose' in f.url)
    enforcement = sum(1 for f in frames if 'enforcement' in f.url)
    print(f"Frames: {len(frames)}, game-core: {game_core}, enforcement: {enforcement}", flush=True)
    for f in frames:
        if 'game-core' in f.url or 'arkose' in f.url or 'enforcement' in f.url:
            print(f"  {f.url[:100]}", flush=True)
    
    page.screenshot(path="force_challenge.png")
    time.sleep(10)
    browser.close()
