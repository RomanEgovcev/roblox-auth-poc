"""Check captcha state - is it solved? What's on the page?"""
import os, time, subprocess, json, sys, base64, io

chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

proc = subprocess.Popen(
    [chrome, f"--user-data-dir={profile}", f"--load-extension={ext}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(6)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Capture all network responses
    auth_responses = []
    page.on("response", lambda r: auth_responses.append({"url": r.url[:200], "status": r.status, "headers": dict(r.headers)}))
    
    page.click("#login-button")
    print("[*] Login submitted", flush=True)
    
    state = "unknown"
    seen_arkose = False
    for i in range(60):
        frames = page.frames
        has_arkose = any('arkoselabs' in f.url for f in frames)
        has_game = any('game-core' in f.url for f in frames)
        if has_arkose:
            seen_arkose = True
        
        page_text = page.evaluate("() => (document.body?.innerText || '').slice(0, 2000)")
        page_url = page.url[:200]
        
        # Check for auth response
        auth_resp = [r for r in auth_responses if 'auth.roblox.com' in r['url']]
        
        status = str(auth_resp[-1]['status']) if auth_resp else 'none'
        print(f"[{i}s] {page_url[:80]} frames:{len(frames)} arkose:{has_arkose} game:{has_game} status:{status}", flush=True)
        
        if 'home' in page_url.lower() or 'games' in page_url.lower():
            print(f"\n[+] REDIRECTED to {page_url}! Captcha solved!", flush=True)
            state = "solved"
            break
        
        if seen_arkose and not has_arkose and i > 10:
            print(f"\n[?] Captcha gone, on {page_url}", flush=True)
            state = "maybe_solved"
            break
        
        time.sleep(1)
    
    print(f"\n=== Final state: {state} ===", flush=True)
    print(f"URL: {page.url[:300]}", flush=True)
    print(f"Text: {page.evaluate('() => (document.body?.innerText || \"\").slice(0, 1000)')[:500]}", flush=True)
    print(f"Frames: {[f.url[:120] for f in page.frames]}", flush=True)
    
    if auth_resp:
        print(f"Auth responses: {[(r['url'][:80], r['status']) for r in auth_resp]}", flush=True)
    
    # Debug: dump full HTML of all frames
    import html as html_mod
    for f in page.frames:
        if 'arkoselabs' in f.url:
            try:
                outer = f.evaluate("() => document.documentElement.outerHTML.slice(0, 5000)")
                print(f"\n--- HTML for {f.url[:100]} ---", flush=True)
                print(outer[:1500], flush=True)
            except Exception as e:
                print(f"[!] Error reading {f.url[:80]}: {e}", flush=True)
    
    # --- SOLVING ---
    game = None
    enf = None
    for f in page.frames:
        if 'game-core' in f.url:
            game = f
        if 'enforcement' in f.url:
            enf = f
    
    if game and enf:
        print(f"\n[>>] Checking both frames...", flush=True)
        # Wait and poll for canvas to appear
        for wait_i in range(20):
            for fname, f in [('game-core', game), ('enforcement', enf)]:
                cinfo = f.evaluate("""() => {
                    const c = document.querySelector('canvas');
                    if (!c) return null;
                    return {w: c.width, h: c.height, w2: c.offsetWidth, h2: c.offsetHeight};
                }""")
                if cinfo:
                    print(f"[{wait_i*2}s] {fname} canvas: {cinfo}", flush=True)
            time.sleep(2)
        
        # Get task from enforcement (text labels, instructions)
        task = enf.evaluate("""() => {
            const every = document.querySelectorAll('*');
            for (const e of every) {
                const t = (e.textContent || '').trim();
                if (t.length > 5 && t.length < 300) return t;
            }
            return 'none';
        }""")
        print(f"Enforcement text: {task[:500]}", flush=True)
        
        task2 = game.evaluate("""() => {
            const every = document.querySelectorAll('*');
            for (const e of every) {
                const t = (e.textContent || '').trim();
                if (t.length > 5 && t.length < 300) return t;
            }
            return 'none';
        }""")
        print(f"Game-core text: {task2[:500]}", flush=True)
        
        # Try to get canvas from either frame
        canvas = None
        for fname, f in [('game-core', game), ('enforcement', enf)]:
            cdata = f.evaluate("""() => {
                const c = document.querySelector('canvas');
                if (!c) return null;
                try { return c.toDataURL('image/png'); }
                catch(e) { return '__tainted__'; }
            }""")
            if cdata and cdata != '__tainted__':
                canvas = cdata
                print(f"[+] Canvas from {fname} via toDataURL", flush=True)
                break
            elif cdata == '__tainted__':
                print(f"[!] {fname} canvas tainted", flush=True)
        
        if not canvas:
            # Try page-level screenshot
            from PIL import Image
            ss = page.screenshot()
            img = Image.open(io.BytesIO(ss))
            canvas_b64 = base64.b64encode(ss).decode()
            canvas = 'data:image/png;base64,' + canvas_b64
            print(f"[!] Fallback: full page screenshot ({len(ss)} bytes)", flush=True)
        
        if canvas and len(canvas) > 100:
            img_data = base64.b64decode(canvas.split(',')[1])
            with open("solve_result.png", "wb") as f:
                f.write(img_data)
            print(f"[*] Saved solve_result.png ({len(img_data)} bytes)", flush=True)
            
            import requests
            proxy = {"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"}
            
            print("[*] Calling NopeCHA API...", flush=True)
            resp = requests.post("https://api.nopecha.com/v1/recognition",
                json={"type": "funcaptcha_match", "task": task, "image_data": [canvas]},
                proxies=proxy, timeout=60)
            
            try:
                result = resp.json()
                print(f"API: {resp.status_code}", flush=True)
                print(json.dumps(result, indent=2, default=str)[:800], flush=True)
                
                if resp.status_code == 200 and result.get('data'):
                    coords = result['data']
                    print(f"\n[++] SOLUTION: {coords}", flush=True)
                    
                    target = game if game else enf
                    for i, (x, y) in enumerate(coords):
                        print(f"  Click {i}: ({x}, {y})", flush=True)
                        target.click("canvas", position={"x": x, "y": y})
                        time.sleep(0.5)
                    
                    print("[+] All clicks done!", flush=True)
                    time.sleep(10)
                    
                    page_url = page.url
                    print(f"URL: {page_url[:200]}", flush=True)
                    if 'home' in page_url.lower():
                        print("\n[!!!] CAPTCHA SOLVED!", flush=True)
                    else:
                        body = page.evaluate("() => (document.body?.innerText || '').slice(0, 500)")
                        print(f"Body: {body[:300]}", flush=True)
                else:
                    print(f"[-] No solution: {result}", flush=True)
            except Exception as e:
                print(f"Error: {e}", flush=True)
                print(resp.text[:500], flush=True)
        else:
            print(f"[-] Canvas empty", flush=True)
    elif not game:
        print("[-] No game-core frame to extract from", flush=True)
    else:
        print("[-] No enforcement frame", flush=True)

proc.kill()
