import os, time
from playwright.sync_api import sync_playwright

ext_path = os.path.abspath(r'C:\Users\regov\Desktop\lua\chromium')
pw_profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=pw_profile,
        headless=False,
        args=[
            f"--load-extension={ext_path}",
        ],
    )
    page = context.pages[0]
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    page.wait_for_selector("#login-username", timeout=60000)
    
    page.fill("#login-username", "CheatingHitmanner")
    page.fill("#login-password", "LolKekZek228")
    page.evaluate("""() => {
        const c = document.getElementById('cookie-banner-wrapper');
        if (c) c.style.display = 'none';
        const bg = document.querySelector('.cookie-banner-bg');
        if (bg) bg.style.display = 'none';
    }""")
    page.wait_for_timeout(500)
    page.click("#login-button", force=True)
    print("[*] Login clicked, waiting...")
    
    for i in range(120):
        time.sleep(2)
        url = page.url
        print(f"  [{i*2+2}s] {url[:80]}")
        
        if "home" in url or "my/dashboard" in url:
            print("[+] LOGIN SUCCESS!")
            for c in context.cookies():
                if c['name'] == '.ROBLOSECURITY':
                    print(f"[+] Cookie: {c['value'][:50]}...")
            break
    else:
        print("[-] No login after 4 minutes")
    
    time.sleep(5)
    context.close()
