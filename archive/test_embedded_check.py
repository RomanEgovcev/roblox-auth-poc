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
    page.click("#login-button", force=True)
    print("[*] Submitted")
    
    last = ""
    for i in range(40):
        time.sleep(1.5)
        info = page.evaluate("""() => {
            const ifs = Array.from(document.querySelectorAll('iframe')).map(f => f.id + '=' + (f.src||'').slice(0,60));
            const a = document.getElementById('arkose-0');
            const ch = document.querySelector('.challenge-captcha-body');
            return {
                ifs: ifs.join('|'),
                arkose: a ? a.outerHTML.slice(0,80) : 'none',
                body: ch ? ch.outerHTML.slice(0,80) : 'none',
                px: document.getElementById('captcha-v2-sensor') ? true : false
            };
        }""")
        s = str(info)
        if s != last:
            print(f"[{i*1.5+1.5}s] {info}")
            last = s
    
    context.close()
