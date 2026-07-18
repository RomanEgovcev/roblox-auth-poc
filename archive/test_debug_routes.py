"""Debug: log ALL route-intercepted URLs looking for challenge."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    # Log ALL routes that contain "challenge" or "v2/login"
    def log_routes(route, request):
        url = request.url
        if any(x in url for x in ("/challenge/", "/v2/login", "pow-puzzle")):
            print(f"[ROUTE] {request.method} {url}", flush=True)
        route.continue_()
    
    page.route("**/*", log_routes)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    page.evaluate("""() => {
        for (let i = 0; i < 30; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 100+i*20, clientY: 200+i*5, bubbles: true}));
        document.querySelector('input[name="username"]')?.focus();
    }""")
    time.sleep(1)
    page.fill('input[name="username"]', 'testuser123')
    time.sleep(0.5)
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    page.evaluate("""() => {
        for (let i = 0; i < 15; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 500+i*20, clientY: 300+i*5, bubbles: true}));
    }""")
    time.sleep(0.5)
    
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
    print(f"Submitted, waiting 20s...", flush=True)
    
    for i in range(20):
        time.sleep(1)
        if i % 5 == 4:
            print(f"[t={i+1}] waiting...", flush=True)
    
    print(f"Done", flush=True)
    browser.close()
