import os, time
from playwright.sync_api import sync_playwright

pw_profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=pw_profile, headless=False,
        args=["--no-proxy-server"],
    )
    
    # Listen for new pages
    context.on("page", lambda new_page: print(f"[POPUP] {new_page.url[:100]}"))
    
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
    print("[*] Submitted")
    
    for i in range(40):
        time.sleep(1)
        # Check all contexts
        for pi, p in enumerate(context.pages):
            for f in p.frames:
                if 'arkoselabs' in f.url or 'funcaptcha' in f.url:
                    print(f"[{i+1}s] FOUND in page {pi}: {f.url[:120]}")
        if len(context.pages) > 1:
            print(f"[{i+1}s] Pages: {len(context.pages)}, extra: {[pp.url[:80] for pp in context.pages[1:]]}")
    
    print("\nFinal state:")
    print(f"  Pages: {len(context.pages)}")
    for pi, q in enumerate(context.pages):
        print(f"  Page {pi}: {q.url[:80]}")
        for f in q.frames:
            print(f"    Frame: {f.url[:100]}")
    
    input("...")
    context.close()
