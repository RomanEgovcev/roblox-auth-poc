"""Test page.click with force=true and verify fill actually works."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    def log_resp(r):
        if any(x in r.url for x in ['auth.roblox.com', 'arkoselabs', '/fc/']):
            t = f"{time.time():.0f}"
            print(f"  [t={t}s {r.status}] {r.url[:200]}", flush=True)
    page.on("response", log_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Verify elements exist
    print("[1] Verifying elements...", flush=True)
    el = page.evaluate("""() => ({
        hasUsername: !!document.querySelector('input[name="username"]'),
        hasPassword: !!document.querySelector('input[name="password"]'),
        hasButton: !!document.getElementById('login-button'),
        usernameRect: document.querySelector('input[name="username"]')?.getBoundingClientRect(),
        buttonRect: document.getElementById('login-button')?.getBoundingClientRect(),
        buttonEnabled: !document.getElementById('login-button')?.disabled,
        buttonClasses: document.getElementById('login-button')?.className?.substring(0, 100),
        viewportW: window.innerWidth,
        viewportH: window.innerHeight,
    })""")
    print(f"  {json.dumps(el, indent=2)[:600]}", flush=True)
    
    # Fill credentials
    print("\n[2] Filling credentials...", flush=True)
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Verify fill worked
    vals = page.evaluate("""() => ({
        username: document.querySelector('input[name="username"]')?.value || '',
        password: document.querySelector('input[name="password"]')?.value || '',
    })""")
    print(f"  Values: {json.dumps(vals)}", flush=True)
    
    # If fill didn't work, try alternate methods
    if not vals.get('username'):
        print("  Fill didn't work, trying type instead...", flush=True)
        page.type("input[name='username']", USER, delay=50)
        page.type("input[name='password']", PASS, delay=50)
        time.sleep(1)
        vals = page.evaluate("""() => ({
            username: document.querySelector('input[name="username"]')?.value || '',
            password: document.querySelector('input[name="password"]')?.value || '',
        })""")
        print(f"  After type: {json.dumps(vals)}", flush=True)
    
    # Click with force=true
    print("\n[3] page.click with force=true...", flush=True)
    try:
        page.click("#login-button", force=True)
        print("  Clicked!", flush=True)
    except Exception as e:
        print(f"  Click error: {e}", flush=True)
    
    # Wait for enforcement
    print("[4] Waiting 60s for enforcement...", flush=True)
    enf = None
    for i in range(120):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf = f
                break
        if enf:
            print(f"  [+] Enforcement at {i*0.5:.0f}s!", flush=True)
            break
        time.sleep(0.5)
    
    if enf:
        print(f"      {enf.url[:120]}", flush=True)
        time.sleep(5)
        gc = None
        for i in range(20):
            for f in page.frames:
                if 'game-core' in f.url:
                    gc = f
                    break
            if gc:
                print(f"  [+] Game-core at {i*0.5:.0f}s!", flush=True)
                break
            time.sleep(0.5)
        if gc:
            state = gc.evaluate("""() => ({
                imgs: document.querySelectorAll('img').length,
                bodyLen: document.body?.innerHTML?.length || 0,
            })""")
            print(f"  GC: {json.dumps(state)}", flush=True)
    else:
        print("  No enforcement after 60s.", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
