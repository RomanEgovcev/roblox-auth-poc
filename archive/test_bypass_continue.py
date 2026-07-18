"""Intercept /challenge/v1/continue and spoof response to skip captcha."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    login_retry = [None]
    continue_body = [None]
    
    # Intercept /challenge/v1/continue to modify response
    def handle_continue(route, request):
        if "/challenge/v1/continue" in request.url and request.method == "POST":
            print(f"[INTERCEPT] /challenge/v1/continue", flush=True)
            continue_body[0] = request.post_data
            
            # Let it go through, catch response via separate handler
            route.continue_()
        else:
            route.continue_()
    
    page.route("**/apis.roblox.com/challenge/v1/continue**", handle_continue)
    
    # Monitor login responses
    def on_resp(resp):
        url = resp.url
        if "/v2/login" in url:
            print(f"[LOGIN RESP] {resp.status}", flush=True)
            if resp.status == 200:
                login_retry[0] = True
                try:
                    body = resp.body()[:500]
                    print(f"  Body: {body}", flush=True)
                except:
                    pass
        elif "/challenge/v1/continue" in url:
            print(f"[CONTINUE RESP] {resp.status}", flush=True)
    page.on("response", on_resp)
    
    # Also try to find PX internal retry function
    def on_console(msg):
        text = msg.text
        if any(x in text for x in ("px", "retry", "token", "Nn", "login")):
            print(f"[CONSOLE] {text[:200]}", flush=True)
    page.on("console", on_console)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    # Mouse interaction
    page.evaluate("""() => {
        for (let i = 0; i < 20; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 100+i*30, clientY: 200+i*10, bubbles: true}));
        document.querySelector('input[name="username"]')?.focus();
        document.querySelector('input[name="username"]')?.dispatchEvent(new Event('focus', {bubbles: true}));
    }""")
    time.sleep(1)
    page.fill('input[name="username"]', 'testuser123')
    time.sleep(0.5)
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    page.evaluate("""() => {
        for (let i = 0; i < 10; i++)
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
    print(f"[t=0] Submitted, waiting for /challenge/v1/continue...", flush=True)
    
    # Wait for /challenge/v1/continue to be intercepted
    # Then fulfill with modified response
    time.sleep(20)
    
    # After /challenge/v1/continue response, also try to call PX retry from JS
    if continue_body[0]:
        print(f"\nContinue body: {continue_body[0]}", flush=True)
        
        # Try to find and call PX retry function
        px_info = page.evaluate("""() => {
            const results = {};
            // Look for PX in window
            if (window._pxpjs) results._pxpjs = Object.keys(window._pxpjs);
            if (window._px) results._px = typeof window._px;
            // Look for retry functions
            const all = [];
            for (const k in window) {
                if (k.toLowerCase().includes('px') || k.toLowerCase().includes('perimeter'))
                    all.push(k);
            }
            results.px_keys = all;
            return results;
        }""")
        print(f"PX info: {px_info}", flush=True)
    
    print(f"\nLogin retry: {login_retry[0]}", flush=True)
    cookies = ctx.cookies()
    rs = [c for c in cookies if ".ROBLOSECURITY" in c["name"]]
    print(f"ROBLOSECURITY: {len(rs)}", flush=True)
    
    time.sleep(5)
    browser.close()
