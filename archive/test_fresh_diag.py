"""Diagnose: fresh profile + extension, check auth response."""
import os, time, subprocess, json, sys

chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_fresh_test"

# Clean start: remove fresh profile
import shutil
if os.path.exists(profile):
    shutil.rmtree(profile)

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
    
    # Capture auth response
    auth_resp = {"status": 0, "url": ""}
    def on_response(r):
        if 'auth.roblox.com' in r.url:
            auth_resp["status"] = r.status
            auth_resp["url"] = r.url[:150]
            print(f"[!] Auth response: {r.status} {r.url[:150]}", flush=True)
    
    page.on("response", on_response)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    page.click("#login-button")
    print("[*] Login submitted", flush=True)
    
    for i in range(60):
        frames = page.frames
        has_arkose = any('arkoselabs' in f.url for f in frames)
        has_game = any('game-core' in f.url for f in frames)
        
        if i % 5 == 0:
            print(f"  [{i}s] frames:{len(frames)} arkose:{has_arkose} game:{has_game} auth:{auth_resp['status']}", flush=True)
        
        if has_game:
            print(f"[+] Game-core at {i}s!", flush=True)
            break
        
        if has_arkose and not has_game and i > 20:
            print(f"[*] Enforcement visible but no game-core after 20s", flush=True)
        
        time.sleep(1)
    else:
        print(f"[-] No captcha in 60s", flush=True)
        print(f"Auth: {auth_resp}", flush=True)
        print(f"URL: {page.url[:200]}", flush=True)
        print(f"Frames: {[f.url[:120] for f in page.frames]}", flush=True)
        
        # Try manually checking if there's a captcha hidden
        try:
            text = page.evaluate("() => document.body?.innerText?.slice(0, 1000) || ''")
            print(f"Page text: {text[:300]}", flush=True)
        except Exception as e:
            print(f"Text error: {e}", flush=True)
        
        proc.kill()
        exit(1)
    
    # Explore game-core
    game_frame = [f for f in page.frames if 'game-core' in f.url][0]
    
    # Get task text
    task = game_frame.evaluate("""() => {
        const all = document.querySelectorAll('*');
        for (const el of all) {
            const t = (el.textContent || '').trim();
            if (t.length > 10 && t.length < 300 &&
                (t.toLowerCase().includes('click') || t.toLowerCase().includes('select') || 
                 t.toLowerCase().includes('choose') || t.toLowerCase().includes('tap') ||
                 t.toLowerCase().includes('image') || t.toLowerCase().includes('picture'))) {
                return t;
            }
        }
        return JSON.stringify([...document.querySelectorAll('*')].map(e => e.textContent?.trim()).filter(t => t && t.length > 5).slice(0, 10));
    }""")
    print(f"Task: {task}", flush=True)
    
    # Canvas
    canvas_info = game_frame.evaluate("""() => {
        const c = document.querySelector('canvas');
        if (!c) return 'no-canvas';
        try {
            return c.toDataURL('image/png').length + ' chars from toDataURL';
        } catch(e) {
            return 'tainted: ' + e.message;
        }
    }""")
    print(f"Canvas: {canvas_info}", flush=True)

proc.kill()
