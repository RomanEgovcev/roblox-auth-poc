"""Verify React fiber walker triggers login."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context()
    page = ctx.new_page()
    
    # Monitor ALL requests
    def on_req(req):
        print(f"[REQ] {req.method} {req.url}", flush=True)
    page.on("request", on_req)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    print("Page loaded", flush=True)
    time.sleep(5)
    
    # Fill form
    page.fill('input[name="username"]', 'testuser123')
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
    # Try to click submit button instead of fiber walker
    submit_btn = page.query_selector('button[type="submit"]')
    if submit_btn:
        print("Found submit button, clicking...", flush=True)
        submit_btn.click()
    else:
        print("No submit button found, trying fiber walker", flush=True)
        page.evaluate("""() => {
            const root = document.querySelector('#login-base') || document.body;
            const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
            if (!key) { console.log('NO_FIBER_KEY'); return; }
            function walk(f, d) {
                if (!f || d > 20) return;
                if (f.memoizedProps && typeof f.memoizedProps.onFormSubmit === 'function') {
                    console.log('FOUND_onFormSubmit');
                    f.memoizedProps.onFormSubmit();
                    return;
                }
                if (f.child) walk(f.child, d+1);
                if (f.sibling) walk(f.sibling, d);
            }
            walk(root[key], 0);
            console.log('WALK_DONE');
        }""")
    
    print("Form submitted, waiting 30s for requests...", flush=True)
    time.sleep(30)
    
    print(f"Done. {browser}, {ctx}", flush=True)
    browser.close()
