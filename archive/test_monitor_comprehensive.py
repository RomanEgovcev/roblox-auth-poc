"""Comprehensive monitor: track ALL post-challenge activity."""
import os, time, json, httpx
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

all_requests = []
websockets = []
px3_before = None
px3_after = None

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"]
    )
    ctx = browser.new_context(bypass_csp=False)
    page = ctx.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("request", lambda r: all_requests.append(f"[REQ] {r.method} {r.url}"))
    page.on("response", lambda r: all_requests.append(f"[RES] {r.status} {r.url}"))
    page.on("websocket", lambda ws: websockets.append(f"[WS] {ws.url}"))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    page.fill('input[name="username"]', 'testuser123')
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
    px3_before = [c for c in ctx.cookies() if c["name"] == "_px3"]
    
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
    print("Login triggered\n", flush=True)
    
    time.sleep(20)
    
    px3_after = [c for c in ctx.cookies() if c["name"] == "_px3"]
    
    print("\n=== ALL REQUESTS ===")
    seen = set()
    for r in all_requests:
        key = r.replace(r.split("=")[-1] if "=" in r else "", "...")
        if key not in seen:
            print(r)
            seen.add(key)
    
    print(f"\n=== WEBSOCKETS ({len(websockets)}) ===")
    for ws in websockets:
        print(ws)
    
    print(f"\n=== _px3 COOKIE ===")
    print(f"Before: {[c['value'][:50] for c in px3_before] if px3_before else 'N/A'}")
    print(f"After:  {[c['value'][:50] for c in px3_after] if px3_after else 'N/A'}")
    
    print(f"\n=== CHALLENGE LOGS ===")
    
    rs = [c for c in ctx.cookies() if c["name"] == ".ROBLOSECURITY"]
    print(f"ROBLOSECURITY: {len(rs)}")
    
    browser.close()
