import os, sys, time
from playwright.sync_api import sync_playwright

username = sys.argv[1] if len(sys.argv) > 1 else "CheatingHitmanner"
password = sys.argv[2] if len(sys.argv) > 2 else ""

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir='pw_profile',
        headless=False,
        args=["--no-proxy-server"],
    )
    page = context.pages[0]
    page.set_default_timeout(15000)

    # Verify extension loaded
    page.goto("chrome://extensions/", wait_until="domcontentloaded")
    time.sleep(1)
    html = page.content()
    if 'NopeCHA' in html:
        print("[+] NopeCHA loaded!", flush=True)
    else:
        print("[-] NopeCHA NOT loaded", flush=True)

    # Go to login
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    page.wait_for_selector("#login-username", timeout=30000)

    # Fill form
    page.fill("#login-username", username)
    page.fill("#login-password", password)
    time.sleep(1)

    # Click login
    for sel in ["button[data-testid='login-button']", "#login-button"]:
        btn = page.query_selector(sel)
        if btn:
            btn.click(force=True)
            print(f"[*] Clicked: {sel}", flush=True)
            break

    print("[*] Observing. Close browser when done.\n", flush=True)

    for i in range(120):
        time.sleep(1)
        url = page.url
        info = f"  [{i+1}s] {url[:70]}"
        try:
            dom = page.evaluate("""() => {
                const arkose = document.querySelector('#arkose-0, .arkose-wrapper');
                const captcha = document.querySelector('iframe[src*="arkoselabs"]');
                const error = document.querySelector('.error-message, .alert-error, [class*="error"]:not([class*="hidden"])');
                return {arkose: !!arkose, captcha: !!captcha, error: error ? error.textContent.trim().slice(0,100) : null};
            }""")
            if dom['arkose'] or dom['captcha']:
                info += " [CAPTCHA]"
            if dom['error']:
                info += f" [ERROR: {dom['error']}]"
        except:
            pass
        print(info, flush=True)
        if "home" in url:
            print("\n[+] LOGGED IN!", flush=True)
            cookies = context.cookies()
            for c in cookies:
                if c['name'] == '.ROBLOSECURITY':
                    print(f"[+] COOKIE: {c['value'][:50]}...")
            break

    context.close()
