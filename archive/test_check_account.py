import os, time
from playwright.sync_api import sync_playwright

pw_profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=pw_profile, headless=False,
        args=["--no-proxy-server"],
    )
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
    print("[*] Submitted. Браузер открыт 120с.")
    for i in range(120):
        time.sleep(1)
        url = page.url
        if 'home' in url:
            print(f"\n[+] LOGGED IN at {i+1}s!")
            for c in context.cookies():
                if c['name'] == '.ROBLOSECURITY':
                    print(f"  Cookie: {c['value'][:60]}...")
            break
    else:
        print(f"\n[-] Время вышло. URL: {page.url[:80]}")
    time.sleep(5)
    context.close()
