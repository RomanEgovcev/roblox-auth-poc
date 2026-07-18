"""Get CSRF token, check eligibleMethods, try realistic click."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    # Use more realistic browser
    browser = p.chromium.launch(
        headless=False,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
        ]
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    page = context.new_page()
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[:200]}", flush=True) if 'auth.roblox.com/v2/login' in r.url or 'arkoselabs' in r.url or 'collector-px' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(2)
    
    # Simulate human-like typing
    page.click("input[name='username']")
    time.sleep(0.5)
    page.type("input[name='username']", USER, delay=80)
    time.sleep(0.3)
    page.click("input[name='password']")
    time.sleep(0.5)
    page.type("input[name='password']", PASS, delay=80)
    time.sleep(1)
    
    # Check for CSRF token
    print("[1] Checking CSRF/ctoken...", flush=True)
    csrf = page.evaluate("""() => {
        const results = {};
        // Check meta csrf
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) results.meta_csrf = meta.content.substring(0, 20);
        
        // Check inputs
        const inputs = document.querySelectorAll('input[type="hidden"]');
        results.hidden_inputs = Array.from(inputs).map(i => ({
            name: i.name, id: i.id, value: (i.value || '').substring(0, 30)
        }));
        
        // Check for __RequestVerificationToken
        const rvt = document.querySelector('input[name="__RequestVerificationToken"]');
        if (rvt) results.rvt = rvt.value.substring(0, 20);
        
        return results;
    }""")
    print(f"  {json.dumps(csrf, indent=2)}", flush=True)
    
    # Try to find eligibleMethods in page context
    try:
        em = page.evaluate("""() => {
            try {
                return typeof eligibleMethods !== 'undefined' ? eligibleMethods : 'not_found';
            } catch(e) {
                return 'error: ' + e.message;
            }
        }""")
        print(f"  eligibleMethods: {em}", flush=True)
    except:
        print("  eligibleMethods: error", flush=True)
    
    # Try to intercept the React login handler's outgoing fetch
    print("\n[2] Setting up fetch interception for login POST...", flush=True)
    watched_requests = []
    page.on("request", lambda r: watched_requests.append({
        'url': r.url[:200], 'method': r.method, 'headers': dict(r.headers)
    }) if 'auth.roblox.com/v2/login' in r.url else None)
    
    # Now click the button in the most realistic way possible
    print("\n[3] Simulating realistic button click...", flush=True)
    btn_box = page.locator("#login-button").bounding_box()
    if btn_box:
        cx = btn_box['x'] + btn_box['width'] / 2
        cy = btn_box['y'] + btn_box['height'] / 2
        page.mouse.move(cx - 50, cy - 50, steps=10)
        time.sleep(0.3)
        page.mouse.move(cx, cy, steps=5)
        time.sleep(0.2)
        page.mouse.click(cx, cy)
        print("  Realistic click done!", flush=True)
    else:
        print("  Button not visible, trying force click", flush=True)
        page.click("#login-button", force=True)
    
    # Wait for enforcement
    print("\n[4] Waiting 60s for enforcement...", flush=True)
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
    else:
        print("  No enforcement.", flush=True)
    
    print(f"\n=== Observed login requests ===", flush=True)
    for r in watched_requests:
        print(f"  [{r['method']}] {r['url']}", flush=True)
        for k, v in r['headers'].items():
            if k.startswith('x-') or k.startswith('rblx') or k == 'content-type':
                print(f"    {k}: {v}", flush=True)
    
    time.sleep(5)
    browser.close()
