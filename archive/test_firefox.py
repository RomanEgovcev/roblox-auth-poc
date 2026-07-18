import os, sys, time
from playwright.sync_api import sync_playwright

ext_path = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
username = sys.argv[1] if len(sys.argv) > 1 else "CheatingHitmanner"
password = sys.argv[2] if len(sys.argv) > 2 else ""

with sync_playwright() as p:
    # Launch Playwright Firefox with proxy AND extension
    browser = p.firefox.launch_persistent_context(
        user_data_dir="C:\\Users\\regov\\Desktop\\lua\\pw_firefox_profile",
        headless=False,
        firefox_user_prefs={
            "network.proxy.type": 5,
        },
    )
    # launch_persistent_context returns a BrowserContext
    ctx = browser
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(15000)
    
    # Test cross-origin fetch
    print("[*] Testing cross-origin fetch in Firefox...", flush=True)
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    result = page.evaluate("""async () => {
        try {
            const resp = await fetch('https://api.nopecha.com/v1/status', { method: 'GET' });
            return 'status: ' + resp.status;
        } catch(e) {
            return 'error: ' + e.message;
        }
    }""")
    print(f"  Fetch test: {result}", flush=True)
    
    # Navigate to roblox login
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    page.wait_for_selector("#login-username", timeout=30000)
    page.fill("#login-username", username)
    page.fill("#login-password", password)
    time.sleep(1)
    for sel in ["button[data-testid='login-button']", "#login-button"]:
        btn = page.query_selector(sel)
        if btn:
            btn.click(force=True)
            print(f"[*] Clicked {sel}", flush=True)
            break
    
    print("[*] Waiting for captcha + auto-solve...", flush=True)
    for i in range(120):
        time.sleep(1)
        url = page.url
        info = f"  [{i+1}s] {url[:70]}"
        try:
            dom = page.evaluate("() => !!document.querySelector('iframe[src*=\"arkoselabs\"]')")
            if dom:
                info += " [CAPTCHA]"
        except:
            pass
        print(info, flush=True)
        if "home" in url:
            print("\n[+] LOGGED IN!", flush=True)
            for c in ctx.cookies():
                if c['name'] == '.ROBLOSECURITY':
                    print(f"[+] COOKIE: {c['value'][:50]}...")
                    print(f"[+] FULL: {c['value']}")
            break
    
    ctx.close()
