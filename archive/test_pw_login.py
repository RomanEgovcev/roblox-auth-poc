import os, sys, time
from playwright.sync_api import sync_playwright

ext_path = os.path.abspath(r'C:\Users\regov\Desktop\lua\chromium_automation')
pw_profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=pw_profile,
        headless=False,
        args=[
            f"--disable-extensions-except={ext_path}",
            f"--load-extension={ext_path}",
        ],
    )
    page = context.pages[0]
    
    # Go to Roblox login
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    page.wait_for_selector("#login-username", timeout=60000)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    page.wait_for_selector("#login-username", timeout=60000)
    
    # Activate extension service worker
    ext_id = "hlnvzeankg3fgvaxrefvy7ezt2xj4qs6"
    print(f"[*] Extension ID: {ext_id}")
    popup = page.context.new_page()
    popup.goto(f"chrome-extension://{ext_id}/assets/ip10n8.html", wait_until="domcontentloaded")
    time.sleep(1)
    popup.close()
    
    # Fill form with React-compatible input
    username = "CheatingHitmanner"
    password = "LolKekZek228"
    
    page.evaluate("""(args) => {
        const [user, pass] = args;
        const u = document.getElementById('login-username');
        const p = document.getElementById('login-password');
        if (!u || !p) return;
        
        const nativeSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;
        
        nativeSetter.call(u, user);
        u.dispatchEvent(new Event('input', {bubbles: true}));
        u.dispatchEvent(new Event('change', {bubbles: true}));
        u.dispatchEvent(new Event('blur', {bubbles: true}));
        
        nativeSetter.call(p, pass);
        p.dispatchEvent(new Event('input', {bubbles: true}));
        p.dispatchEvent(new Event('change', {bubbles: true}));
        p.dispatchEvent(new Event('blur', {bubbles: true}));
    }""", [username, password])
    
    time.sleep(1)
    
    # Hide cookie banner
    page.evaluate("""() => {
        const c = document.getElementById('cookie-banner-wrapper');
        if (c) c.style.display = 'none';
    }""")
    
    # Click login
    login_btn = page.query_selector("button[type='submit'], #login-button")
    if login_btn:
        login_btn.click(force=True)
    
    print("Waiting for captcha or redirect...")
    
    # Poll for up to 90 seconds
    for i in range(90):
        time.sleep(1)
        url = page.url
        print(f"  [{i+1}s] URL: {url[:100]}")
        
        if "home" in url or "my/dashboard" in url:
            print("[+] LOGIN SUCCESS!")
            cookies = context.cookies()
            for c in cookies:
                if c['name'] == '.ROBLOSECURITY':
                    print(f"[+] Cookie: {c['value'][:50]}...")
                    break
            break
        
        # Check for captcha
        captcha = page.query_selector("#arkose-0, iframe[src*='arkoselabs'], [data-pk], .arkose-wrapper")
        if captcha and not captcha.is_hidden():
            print(f"[*] Captcha detected at {i+1}s")
        
        # Check for error
        error = page.query_selector(".error-message, .alert-error, .login-error")
        if error and error.is_visible():
            txt = error.text_content()
            if txt and ("incorrect" in txt.lower() or "invalid" in txt.lower() or "невер" in txt.lower()):
                print(f"[-] Wrong password: {txt}")
                break
    
    time.sleep(30)
    context.close()
    print("Done")
