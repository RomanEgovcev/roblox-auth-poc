"""Explore game-core iframe structure + test NopeCHA API call."""
import os, time, subprocess, json, sys, base64

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
    page.click("#login-button")
    print("[*] Login submitted, waiting for game-core...", flush=True)
    
    game_frame = None
    for i in range(60):
        for f in page.frames:
            if 'game-core' in f.url:
                game_frame = f
                break
        if game_frame:
            print(f"[+] Game-core at {i}s: {game_frame.url[:200]}", flush=True)
            break
        time.sleep(1)
    else:
        print("[-] No game-core in 60s", flush=True)
        proc.kill()
        exit(1)
    
    # Give it a moment to fully load
    time.sleep(2)
    
    # Explore game-core HTML - full body
    try:
        html = game_frame.evaluate("() => document.body?.innerHTML || ''")
        print(f"\n=== Game-core HTML ({len(html)} chars) ===", flush=True)
        print(html[:5000], flush=True)
    except Exception as e:
        print(f"  HTML error: {e}", flush=True)
    
    # Try different selectors for task text
    for selector in ['.challenge-text', '.prompt-text', '.task-text', 
                     '[class*="task"]', '[class*="challenge"]', '[class*="prompt"]',
                     '[class*="instruction"]', '[class*="description"]',
                     'h1', 'h2', 'h3', 'h4', '[data-task]',
                     '#task', '#challenge']:
        try:
            el = game_frame.evaluate(f"""() => {{
                const e = document.querySelector('{selector}');
                if (!e) return null;
                return {{ tag: e.tagName, text: e.textContent?.slice(0, 200), class: e.className }};
            }}""")
            if el:
                print(f"  [{selector}] -> {json.dumps(el, ensure_ascii=False)}", flush=True)
        except:
            pass
    
    # Check for canvas
    canvas_info = game_frame.evaluate("""() => {
        const c = document.querySelector('canvas');
        if (!c) return {exists: false};
        const rect = c.getBoundingClientRect();
        const ctx = c.getContext('2d');
        const imgData = ctx ? 'has-data' : 'no-2d-ctx';
        return {
            exists: true,
            width: c.width,
            height: c.height,
            rect: {top: rect.top, left: rect.left, width: rect.width, height: rect.height},
            ctx2d: !!ctx,
            imgData: imgData
        };
    }""")
    print(f"\n=== Canvas info ===", flush=True)
    print(json.dumps(canvas_info, indent=2, default=str), flush=True)
    
    # If canvas has 2D context, try to extract its data
    if canvas_info.get('ctx2d'):
        try:
            canvas_data = game_frame.evaluate("""() => {
                const c = document.querySelector('canvas');
                if (!c) return null;
                return c.toDataURL('image/png');
            }""")
            print(f"\nCanvas dataURL length: {len(canvas_data)} chars", flush=True)
            if len(canvas_data) > 1000:
                # Save the image
                img_bytes = base64.b64decode(canvas_data.split(',')[1])
                with open("game_canvas.png", "wb") as f:
                    f.write(img_bytes)
                print(f"Canvas image saved: {len(img_bytes)} bytes -> game_canvas.png", flush=True)
        except Exception as e:
            print(f"  Canvas data error: {e}", flush=True)
    
    # Check all text in game frame
    all_text = game_frame.evaluate("""() => {
        const all = document.querySelectorAll('*');
        const texts = [];
        for (const el of all) {
            if (el.textContent && el.textContent.trim().length > 5 && 
                el.childElementCount === 0) {  // leaf nodes only
                texts.push(el.textContent.trim().slice(0, 100));
            }
        }
        return texts.slice(0, 30);
    }""")
    print(f"\n=== All text nodes ===", flush=True)
    for t in all_text:
        print(f"  {t}", flush=True)
    
    print("\nDone. Check game_canvas.png and HTML output.", flush=True)

proc.kill()
