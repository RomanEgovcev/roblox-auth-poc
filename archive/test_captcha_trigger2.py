import os, time
from playwright.sync_api import sync_playwright

pw_profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=pw_profile, headless=False,
    )
    page = context.pages[0]
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    page.wait_for_selector("#login-username", timeout=60000)
    page.fill("#login-username", "CheatingHitmanner")
    page.fill("#login-password", "LolKekZek228")
    page.evaluate("""() => {
        document.querySelectorAll('.cookie-banner-wrapper, .cookie-banner-bg, .notification-blue')
            .forEach(e => { if (e) e.style.display = 'none'; });
    }""")
    page.wait_for_timeout(500)
    page.click("#login-button", force=True)
    print("[*] Clicked. Watching frames...")
    
    for i in range(30):
        time.sleep(1)
        for f in page.frames:
            if 'arkoselabs' in f.url:
                print(f"[{i+1}s] CAPTCHA FRAME: {f.url[:120]}")
            elif 'ec-game-core' in f.url:
                print(f"[{i+1}s] GAME CORE FRAME: {f.url[:120]}")
        # Also check DOM for captcha container
        arkose = page.evaluate("document.getElementById('arkose-0')?.outerHTML?.slice(0,100)")
        if arkose and 'display: none' not in arkose:
            print(f"[{i+1}s] ARKOSE VISIBLE: {arkose}")
        elif arkose:
            print(f"[{i+1}s] ARKOSE (hidden): {arkose}")
