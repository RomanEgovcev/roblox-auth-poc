import os, time
from playwright.sync_api import sync_playwright

pw_profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=pw_profile, headless=False,
        args=["--no-proxy-server"],
    )
    
    context.on("page", lambda pp: print(f"[POPUP] {pp.url[:100]}"))
    
    page = context.pages[0]
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    page.wait_for_selector("#login-username", timeout=30000)
    page.fill("#login-username", "TestAccountOpenCode")
    page.fill("#login-password", "TestAccountOpenCode123")
    page.evaluate("""() => {
        document.querySelectorAll('.cookie-banner-wrapper, .cookie-banner-bg, .notification-blue')
            .forEach(e => { if (e && e.style) e.style.display = 'none'; });
    }""")
    page.wait_for_timeout(500)
    page.click("#login-button", force=True)
    print("[*] Submitted. Смотри экран.")
    print("[*] Если появится капча - напиши, я проверю что видит Playwright")
    
    for i in range(30):
        time.sleep(1)
        found = []
        for pp in context.pages:
            for ff in pp.frames:
                url = ff.url
                if 'arkoselabs' in url or 'funcaptcha' in url or 'captcha' in url.lower():
                    found.append((pp.url[:60], url[:100]))
        if found:
            print(f"[{i+1}s] FOUND: {found}")
        if len(context.pages) > 1:
            print(f"[{i+1}s] Extra pages: {[q.url[:60] for q in context.pages[1:]]}")
    
    print("\nFinal:")
    for pi, q in enumerate(context.pages):
        print(f"  Page {pi}: {q.url[:80]}")
        for ff in q.frames:
            if 'about:blank' not in ff.url and 'roblox.com/login' not in ff.url:
                print(f"    Frame: {ff.url[:110]}")
    
    context.close()
