"""Test: simulate human behavior to avoid PX delay."""
import os, time, random, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    t0 = [None]
    
    def on_req(req):
        if t0[0] is None:
            return
        dt = time.time() - t0[0]
        if any(x in req.url for x in ("/v2/login", "pow-puzzle", "challenge/v1", "px-cloud", "main.min", "worker-resources", "account-security")):
            marker = ""
            if "/v2/login" in req.url: marker = " ** LOGIN **"
            print(f"[{dt:6.2f}s] {req.method} {req.url[:120]}{marker}", flush=True)
    page.on("request", on_req)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    
    # Wait for page fully loaded + PX initialized
    time.sleep(5)
    
    # Simulate natural human behavior
    page.evaluate("""() => {
        // Move mouse around the page
        const dispatch = (type, x, y) => {
            document.dispatchEvent(new MouseEvent(type, {clientX: x, clientY: y, bubbles: true}));
        };
        for (let i = 0; i < 20; i++) {
            dispatch('mousemove', 100 + i * 30, 200 + i * 10);
        }
        // Click on username field
        const u = document.querySelector('input[name="username"]');
        if (u) {
            u.focus();
            u.dispatchEvent(new Event('focus', {bubbles: true}));
        }
    }""")
    time.sleep(1)
    
    page.fill('input[name="username"]', 'testuser123')
    time.sleep(0.5)
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
    # More mouse movement
    page.evaluate("""() => {
        const dispatch = (type, x, y) => {
            document.dispatchEvent(new MouseEvent(type, {clientX: x, clientY: y, bubbles: true}));
        };
        for (let i = 0; i < 10; i++) {
            dispatch('mousemove', 500 + i * 20, 300 + i * 5);
        }
    }""")
    time.sleep(1)
    
    page.evaluate("""() => {
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        function walk(f, d) {
            if (!f || d > 20) return null;
            if (f.memoizedProps && typeof f.memoizedProps.onFormSubmit === 'function') {
                f.memoizedProps.onFormSubmit();
                return 'ok';
            }
            return walk(f.child, d+1) || walk(f.sibling, d);
        }
        return walk(root[key], 0);
    }""")
    t0[0] = time.time()
    print(f"[t=0] onFormSubmit called", flush=True)
    
    # Wait up to 20 seconds (to see if delay is shorter with human interaction)
    for i in range(20):
        time.sleep(1)
        # Check if login happened
        has_login = page.evaluate("""() => {
            // Check if challenge is visible
            return document.querySelector('.challenge-container') !== null;
        }""")
        if has_login:
            print(f"[t={i+1}s] Challenge visible!", flush=True)
            break
    
    # Keep waiting for full challenge resolution
    time.sleep(40)
    print(f"\nDone", flush=True)
    browser.close()
