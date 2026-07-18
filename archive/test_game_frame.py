import os, time, base64, requests
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
        const c = document.getElementById('cookie-banner-wrapper');
        if (c) c.style.display = 'none';
        const bg = document.querySelector('.cookie-banner-bg');
        if (bg) bg.style.display = 'none';
    }""")
    page.wait_for_timeout(500)
    page.click("#login-button", force=True)
    print("[*] Login clicked")
    
    # Wait for enforcement iframe
    enforcement_frame = None
    for i in range(30):
        time.sleep(1)
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url:
                enforcement_frame = f
                print(f"[*] Enforcement frame at {i+1}s: {f.url[:120]}")
                break
        if enforcement_frame:
            break
    
    if not enforcement_frame:
        print("[-] No enforcement frame")
        context.close()
        exit()
    
    # Wait for game-core-frame to render inside
    game_frame = None
    for i in range(30):
        time.sleep(1)
        if enforcement_frame.child_frames:
            game_frame = enforcement_frame.child_frames[0]
            print(f"[*] Game frame at +{i+1}s: {game_frame.url[:120]}")
            break
    
    if game_frame:
        # Get canvas data
        canvas_b64 = game_frame.evaluate("""() => {
            const c = document.querySelector('canvas');
            if (c) return c.toDataURL('image/png');
            return null;
        }""")
        print(f"[*] Canvas: {'found (' + str(len(canvas_b64)) + ' chars)' if canvas_b64 else 'none'}")
        
        # Get all visible elements
        info = game_frame.evaluate("""() => {
            return Array.from(document.querySelectorAll('*')).slice(0, 30).map(el => ({
                tag: el.tagName,
                id: el.id,
                cls: (typeof el.className === 'string' ? el.className : '').slice(0, 50),
                text: (el.textContent || '').trim().slice(0, 100),
                rect: el.getBoundingClientRect ? JSON.stringify({w:el.offsetWidth, h:el.offsetHeight, v:el.checkVisibility()}) : ''
            }));
        }""")
        for el in info:
            if el['id'] or el['text']:
                print(f"  <{el['tag']}> id={el['id']} txt={el['text']} rect={el['rect']}")
    
        # Get string-table (task description found here earlier)
        table = enforcement_frame.evaluate("""() => {
            const el = document.getElementById('string-table');
            return el ? el.value : null;
        }""")
        if table:
            print(f"[*] string-table ({len(table)} chars)")
    
    time.sleep(5)
    context.close()
