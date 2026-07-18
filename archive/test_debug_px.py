"""Debug PX + enforcement loading with detailed logging."""
import os, time, json, sys

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    all_requests = []
    all_frames = []
    
    page.on("request", lambda r: all_requests.append(f"[{r.method}] {r.url[:200]}"))
    page.on("response", lambda r: all_requests.append(f"[{r.status}] {r.url[:200]}"))
    page.on("frameattached", lambda f: all_frames.append(f"ATTACHED: {f.url[:200]}"))
    page.on("framenavigated", lambda f: all_frames.append(f"NAVIGATED: {f.url[:200]}"))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    print("[1] Page loaded, waiting 10s for PX init...", flush=True)
    time.sleep(10)
    
    # Check PX state
    px_state = page.evaluate("""() => {
        const result = {};
        result.hasPX = typeof _px !== 'undefined';
        result.pxType = typeof _px;
        result.pxKeys = _px ? Object.keys(_px).join(', ') : 'N/A';
        
        // Check challenge.js version
        const scripts = Array.from(document.scripts);
        result.pxScript = scripts.filter(s => s.src.includes('main.min.js')).map(s => s.src.substring(0, 200)).join(', ');
        
        // Check if challenge middleware loaded
        result.hasChallengeMiddleware = typeof genericChallengeMiddlewareType !== 'undefined' || typeof PX !== 'undefined';
        
        return result;
    }""")
    print(f"  PX state: {json.dumps(px_state)}", flush=True)
    
    # Check CSP
    csp = page.evaluate("""() => {
        const meta = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
        return meta ? meta.content : 'none';
    }""")
    print(f"  CSP: {csp[:200]}", flush=True)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(2)
    
    # Dispatch Enter
    print("\n[2] Dispatching Enter...", flush=True)
    page.evaluate("""() => {
        const pw = document.querySelector('input[name="password"]');
        if (!pw) return;
        ['keydown','keypress','keyup'].forEach(evt => {
            pw.dispatchEvent(new KeyboardEvent(evt, {
                key: 'Enter', code: 'Enter', keyCode: 13, which: 13,
                bubbles: true, cancelable: true
            }));
        });
    }""")
    
    print("  Waiting 15s for enforcement...", flush=True)
    time.sleep(15)
    
    print(f"\n=== Frames ({len(page.frames)}) ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    print(f"\n=== All events (last 30) ===", flush=True)
    for e in all_requests[-30:]:
        print(f"  {e}", flush=True)
    
    print(f"\n=== Frame events (last 20) ===", flush=True)
    for e in all_frames[-20:]:
        print(f"  {e}", flush=True)
    
    browser.close()
