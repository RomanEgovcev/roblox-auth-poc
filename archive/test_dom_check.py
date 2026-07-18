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
    print("[*] Submitted. Жми Enter когда капча появится...")
    
    # Loop watching for frames
    for i in range(60):
        time.sleep(1)
        # Check all frames in ALL pages
        found = False
        for pp in context.pages:
            for ff in pp.frames:
                if 'arkoselabs' in ff.url or 'funcaptcha' in ff.url or 'ec-game-core' in ff.url:
                    print(f"[{i+1}s] FRAME: {ff.url[:120]}")
                    found = True
        # Also check DOM for iframe elements
        iframes = page.evaluate("""() => {
            const ifs = document.querySelectorAll('iframe');
            return Array.from(ifs).slice(0, 10).map(f => 
                f.id + ' src=' + (f.src || 'none').slice(0, 80) + ' visible=' + f.checkVisibility()
            );
        }""")
        for ifr in iframes:
            print(f"  [{i+1}s] IFRAME: {ifr}")
        
        # Check shadow roots
        shadow = page.evaluate("""() => {
            const els = document.querySelectorAll('*');
            for (const el of els) {
                if (el.shadowRoot) return 'SHADOW on <' + el.tagName + '>#' + el.id;
            }
            return null;
        }""")
        if shadow:
            print(f"  [{i+1}s] {shadow}")
    
    context.close()
