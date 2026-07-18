import os, sys, time, requests, base64
from playwright.sync_api import sync_playwright

pw_profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=pw_profile,
        headless=False,
    )
    page = context.pages[0]
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    page.wait_for_selector("#login-username", timeout=60000)
    
    username = "CheatingHitmanner"
    password = "LolKekZek228"
    page.fill("#login-username", username)
    page.fill("#login-password", password)
    
    # Hide cookie banner
    page.evaluate("""() => {
        const c = document.getElementById('cookie-banner-wrapper');
        if (c) c.style.display = 'none';
        const bg = document.querySelector('.cookie-banner-bg');
        if (bg) bg.style.display = 'none';
    }""")
    page.wait_for_timeout(500)
    
    page.click("#login-button", force=True)
    print("[*] Login clicked")
    
    # Poll for captcha iframe
    iframe_elem = None
    for i in range(20):
        time.sleep(1)
        iframe_elem = page.query_selector("iframe[src*='arkoselabs']")
        if iframe_elem:
            print(f"[*] Captcha iframe found at {i+1}s")
            break
    
    if not iframe_elem:
        print("[-] No captcha iframe found")
        context.close()
        exit()
    
    # Wait for challenge to fully render
    time.sleep(10)
    
    # Find the frame in page.frames
    frame = None
    for f in page.frames:
        if 'arkoselabs' in f.url:
            frame = f
            print(f"[*] Found frame: {f.url[:120]}")
            break
    
    if not frame and iframe_elem:
        frame = iframe_elem.content_frame()
    
    if frame:
        print(f"[*] Frame URL: {frame.url[:120]}")
        
        # List all elements with ids, classes, or text
        info = frame.evaluate("""() => {
            const all = document.querySelectorAll('*');
            const result = [];
            all.forEach(el => {
                const tag = el.tagName;
                const id = el.id;
                const cls = el.className;
                const text = (el.textContent || '').trim().slice(0, 100);
                if (id || cls || text) {
                    result.push({tag, id: id || '', cls: (typeof cls === 'string' ? cls : '').slice(0, 50), text: text.slice(0, 80)});
                }
            });
            return result.slice(0, 150);
        }""")
        
        for el in info:
            print(f"  <{el['tag']}> id={el['id']} cls={el['cls'][:50]} text={el['text'][:60]}")
        
        # Also take screenshot of iframe
        page.screenshot(path="captcha_screenshot.png")
        print("[*] Screenshot saved")
    
    time.sleep(10)
    context.close()
    print("Done")
