"""Direct fetch to trigger PX, then wait for enforcement frames."""
import os, time, json, re

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Step 1: Get CSRF
    print("[*] Step 1: Get CSRF token...", flush=True)
    csrf = page.evaluate("""async () => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
        });
        return r.headers.get('x-csrf-token');
    }""")
    print(f"  CSRF: {csrf}", flush=True)
    
    if not csrf:
        print("[-] No CSRF token obtained", flush=True)
        browser.close()
        exit(1)
    
    # Step 2: POST with CSRF to trigger PX challenge
    print("[*] Step 2: Trigger PX challenge...", flush=True)
    challenge = page.evaluate("""async (csrf) => {
        try {
            const r = await fetch('https://auth.roblox.com/v2/login', {
                method: 'POST', credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'x-csrf-token': csrf
                },
                body: JSON.stringify({
                    ctype: 'Username',
                    cvalue: 'testuser123',
                    password: 'wrongpass123!'
                })
            });
            const text = await r.text();
            console.log('CHALLENGE RESPONSE:', r.status, text.substring(0, 500));
            return {status: r.status, body: text, headers: [...r.headers.entries()]};
        } catch(e) {
            console.log('CHALLENGE ERROR:', e.message);
            return {error: e.message};
        }
    }""", csrf)
    print(f"  Status: {challenge.get('status')}", flush=True)
    print(f"  Body: {challenge.get('body','')[:300]}", flush=True)
    
    if challenge.get('status') == 403 and 'challenge' in challenge.get('body','').lower():
        print("[*] PX challenge triggered!", flush=True)
        
        # Wait for enforcement frames
        print("[*] Waiting for enforcement frames...", flush=True)
        for i in range(90):
            enf_frames = [f for f in page.frames if 'enforcement' in f.url]
            game_frames = [f for f in page.frames if 'game-core' in f.url or 'arkoselabs' in f.url]
            if i % 10 == 0:
                print(f"[{i}s] frames:{len(page.frames)} enf:{len(enf_frames)} game:{len(game_frames)}", flush=True)
                # Also check for any challenge divs
            if game_frames:
                print(f"[++] GAME-CORE: {game_frames[0].url[:150]}", flush=True)
                break
            time.sleep(1)
        else:
            print("[-] No enforcement/game-core frames", flush=True)
            page.screenshot(path="noenf.png")
    else:
        print(f"[?] Unexpected response: {challenge}", flush=True)
        page.screenshot(path="unexpected.png")
    
    input("Enter...")
    browser.close()
