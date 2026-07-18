"""Understand timing: how long does challenge flow take?"""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    events = []
    def on_resp(resp):
        url = resp.url
        t = time.time()
        if "/v2/login" in url and resp.status == 403:
            events.append((t, "403_CHALLENGE", resp.headers.get("rblx-challenge-id","")))
        elif "pow-puzzle" in url and resp.request.method == "GET":
            events.append((t, "PUZZLE_GET", url))
        elif "pow-puzzle" in url and "/verify" in url and resp.request.method == "POST":
            events.append((t, "PUZZLE_VERIFY", url))
        elif "/challenge/v1/continue" in url:
            events.append((t, "CONTINUE", url))
    
    page.on("response", on_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    
    page.fill('input[name="username"]', 'testuser123')
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
    page.evaluate("""() => {
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        if (!key) return;
        function walk(f, d) {
            if (!f || d > 20) return;
            if (f.memoizedProps && typeof f.memoizedProps.onFormSubmit === 'function') {
                f.memoizedProps.onFormSubmit();
                return;
            }
            if (f.child) walk(f.child, d+1);
            if (f.sibling) walk(f.sibling, d);
        }
        walk(root[key], 0);
    }""")
    t0 = time.time()
    print(f"Login triggered at t=0", flush=True)
    
    time.sleep(60)
    
    print(f"\nTimeline (t0={t0:.0f}):", flush=True)
    events.sort(key=lambda x: x[0])
    for evt in events:
        dt = evt[0] - t0
        print(f"  t={dt:6.1f}s  {evt[1]}  {evt[2][:50]}", flush=True)
    
    browser.close()
