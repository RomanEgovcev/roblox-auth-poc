import os, time, requests
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
    
    # Wait for captcha + game frame
    game_frame = None
    for i in range(15):
        time.sleep(2)
        print(f"  [{i*2+2}s] frames: {[f.url[:60] for f in page.frames]}")
        for f in page.frames:
            if 'game-core-frame' in f.url or 'game' in f.url or 'fc/game' in f.url or 'cdn' in f.url:
                game_frame = f
                print(f"[*] Found game frame: {f.url[:120]}")
                break
        if game_frame:
            break
    
    if game_frame:
        # Try to get canvas
        canvas_b64 = game_frame.evaluate("""() => {
            const c = document.querySelector('canvas');
            if (c) return c.toDataURL('image/png');
            const imgs = document.querySelectorAll('img');
            for (const img of imgs) {
                if (img.src && img.src.startsWith('data:')) return img.src;
            }
            return null;
        }""")
        
        task = game_frame.evaluate("""() => {
            const el = document.querySelector('[data-task], [data-challenge], .challenge-text, .instruction');
            return el ? (el.textContent || el.getAttribute('data-task') || el.getAttribute('data-challenge')).trim().slice(0, 200) : null;
        }""")
        
        print(f"[*] Canvas: {'found' if canvas_b64 else 'none'}")
        print(f"[*] Task: {task}")
        
        if canvas_b64 and task:
            print("[*] Submitting to NopeCHA...")
            r = requests.post("https://api.nopecha.com/v1/recognition/funcaptcha", json={
                "task": task,
                "image_data": [canvas_b64]
            }, timeout=30)
            print(f"  API: {r.status_code} {r.text[:200]}")
    
    time.sleep(5)
    context.close()
