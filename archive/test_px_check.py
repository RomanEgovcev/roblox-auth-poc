import os, time
from playwright.sync_api import sync_playwright

pw_profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=pw_profile, headless=False,
    )
    page = context.pages[0]
    
    # 1. Check if PX sensor loads on fresh navigation
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(5)
    px = page.evaluate("""() => {
        const s = document.getElementById('captcha-v2-sensor');
        return s ? s.src : 'not found';
    }""")
    print(f"[*] PX sensor script: {px}")
    
    arkose = page.evaluate("""() => {
        const a = document.getElementById('arkose-0');
        return a ? a.outerHTML.slice(0, 150) : 'not found';
    }""")
    print(f"[*] Arkose container: {arkose}")
    
    # 2. Fill form and submit
    page.fill("#login-username", "CheatingHitmanner")
    page.fill("#login-password", "LolKekZek228")
    page.evaluate("""() => {
        document.querySelectorAll('.cookie-banner-wrapper, .cookie-banner-bg, .notification-blue')
            .forEach(e => { if (e && e.style) e.style.display = 'none'; });
    }""")
    page.click("#login-button", force=True)
    
    # 3. Monitor for 30s
    for i in range(30):
        time.sleep(1)
        for f in page.frames:
            if 'arkoselabs' in f.url:
                print(f"[{i+1}s] FRAME: {f.url[:120]}")
        px = page.evaluate("document.getElementById('captcha-v2-sensor')?.src || 'none'")
        ak = page.evaluate("document.getElementById('arkose-0')?.outerHTML?.slice(0,120) || 'none'")
        if 'arkoselabs' in str(page.frames) or 'arkoselabs' in ak:
            print(f"  PX: {px.split('/')[-1][:30]}  Arkose: {ak}")
    
    print(f"\nFinal URL: {page.url[:80]}")
    input("Enter...")
    context.close()
