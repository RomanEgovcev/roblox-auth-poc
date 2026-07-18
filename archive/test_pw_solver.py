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
    
    # Fill form using Playwright's built-in fill()
    username = "CheatingHitmanner"
    password = "LolKekZek228"
    
    page.fill("#login-username", username)
    page.fill("#login-password", password)
    print(f"[*] Fields filled: u={username} p={password}")
    
    time.sleep(1)
    
    # Hide cookie banner with delay
    page.evaluate("""() => {
        const c = document.getElementById('cookie-banner-wrapper');
        if (c) c.style.display = 'none';
        const bg = document.querySelector('.cookie-banner-bg');
        if (bg) bg.style.display = 'none';
    }""")
    page.wait_for_timeout(500)
    
    page.screenshot(path="before_click.png")
    print("[*] Screenshot saved: before_click.png")
    
    # Click login
    page.click("#login-button", force=True)
    print("[*] Login button clicked")
    
    # Check page after click
    time.sleep(3)
    print(f"[*] After click URL: {page.url}")
    print(f"[*] After click title: {page.title()}")
    with open("after_click.html", "w", encoding="utf-8") as f:
        f.write(page.content())
    
    print("Waiting for captcha or redirect...")
    
    solved = False
    for i in range(90):
        time.sleep(1)
        url = page.url
        print(f"  [{i+1}s] URL: {url[:100]}")
        
        if "home" in url or "my/dashboard" in url:
            print("[+] LOGIN SUCCESS!")
            for c in context.cookies():
                if c['name'] == '.ROBLOSECURITY':
                    print(f"[+] Cookie: {c['value'][:50]}...")
                    solved = True
                    break
            break
        
        # Detect captcha iframe
        iframe_elem = page.query_selector("iframe[src*='arkoselabs']")
        if iframe_elem and not solved:
            print(f"[*] Captcha iframe found at {i+1}s")
            
            # Get the frame
            frame = iframe_elem.content_frame()
            if frame:
                print(f"[*] Frame URL: {frame.url[:120]}")
                
                # Dump frame content for analysis
                html = frame.content()
                with open("iframe_debug.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print("[*] Saved iframe_debug.html")
                
                # Try to extract task and image
                try:
                    task = frame.evaluate("""() => {
                        const el = document.querySelector('[data-task]');
                        return el ? el.getAttribute('data-task') : null;
                    }""")
                    print(f"[*] Task: {task}")
                    
                    # Try canvas screenshot
                    img_b64 = frame.evaluate("""() => {
                        const c = document.querySelector('canvas');
                        if (c) return c.toDataURL('image/jpeg', 0.8);
                        // Try img elements
                        const imgs = document.querySelectorAll('img');
                        if (imgs.length) return imgs[0].src;
                        return null;
                    }""")
                    if img_b64:
                        print(f"[*] Image data: {img_b64[:80]}...")
                        
                        # Submit to NopeCHA
                        print("[*] Submitting to NopeCHA API...")
                        r = requests.post(
                            "https://api.nopecha.com/v1/recognition/funcaptcha",
                            json={
                                "task": task or "Select the correct image",
                                "image_data": [img_b64]
                            },
                            timeout=30
                        )
                        print(f"  API response: {r.status_code} {r.text[:200]}")
                        
                        if r.status_code == 200:
                            job_id = r.json()["data"]
                            print(f"[*] Job ID: {job_id}")
                            
                            for j in range(60):
                                time.sleep(1)
                                r2 = requests.get(
                                    f"https://api.nopecha.com/v1/recognition/funcaptcha?id={job_id}",
                                    timeout=30
                                )
                                r2j = r2.json()
                                if "data" in r2j:
                                    tiles = r2j["data"]
                                    print(f"[*] Solution: {tiles}")
                                    # Click tiles
                                    frame.evaluate("""(tiles) => {
                                        const tiles_els = document.querySelectorAll('[data-tile], .tile, button[role]');
                                        console.log('Tile elements:', tiles_els.length);
                                        tiles_els.forEach((el, i) => {
                                            console.log('Tile', i, el.outerHTML.slice(0,100));
                                        });
                                        // Try clicking
                                        tiles_els.forEach((el, i) => {
                                            if (tiles[i] && el) el.click();
                                        });
                                    }""", tiles)
                                    
                                    # Submit
                                    frame.evaluate("""() => {
                                        const btn = document.querySelector('[data-action=verify], [data-action=submit], button:contains("Verify")');
                                        if (btn) btn.click();
                                    }""")
                                    print("[*] Tiles clicked, verifying...")
                                    break
                                elif "error" in r2j:
                                    print(f"  Error: {r2j}")
                                    break
                except Exception as ex:
                    print(f"[-] Frame eval error: {ex}")
                    import traceback
                    traceback.print_exc()
        
        # Check for error
        error = page.query_selector(".error-message, .alert-error, .login-error")
        if error and error.is_visible():
            txt = error.text_content()
            if txt and ("incorrect" in txt.lower() or "invalid" in txt.lower() or "невер" in txt.lower()):
                print(f"[-] Wrong password: {txt}")
                break
    
    time.sleep(10)
    context.close()
    print("Done")
