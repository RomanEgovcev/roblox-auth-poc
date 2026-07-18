"""Full solution: create enforcement, load game-core, extract captcha data."""
import os, time, json, sys, re

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(8)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(2)
    
    # Prime + trigger enforcement
    print("[1] Priming PX with Enter events...", flush=True)
    for _ in range(3):
        page.evaluate("""() => {
            const pw = document.querySelector('input[name="password"]');
            if (!pw) return;
            ['keydown','keypress','keyup'].forEach(evt => {
                pw.dispatchEvent(new KeyboardEvent(evt, {
                    key: 'Enter', code: 'Enter', keyCode: 13,
                    bubbles: true, cancelable: true
                }));
            });
        }""")
        time.sleep(1)
    
    print("[2] Dispatching click to create enforcement...", flush=True)
    for attempt in range(10):
        enf_frames = [f for f in page.frames if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url]
        if enf_frames:
            print(f"  Enforcement found!", flush=True)
            break
        
        page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            if (btn) btn.dispatchEvent(new MouseEvent('click', {
                bubbles: true, cancelable: true, view: window
            }));
        }""")
        
        for i in range(12):
            enf_frames = [f for f in page.frames if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url]
            if enf_frames:
                break
            time.sleep(0.5)
    
    if not enf_frames:
        print("  No enforcement. Exiting.", flush=True)
        browser.close()
        exit()
    
    enf = enf_frames[0]
    st = re.search(r'&([0-9a-f\-]{36})$', enf.url)
    print(f"  Session: {st.group(1) if st else 'none'}", flush=True)
    time.sleep(5)
    
    # Trigger React onClick to load game-core
    print("[3] Loading game-core via React onClick...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        const propsKey = Object.keys(btn).find(k => k.startsWith('__reactProps'));
        if (propsKey && btn[propsKey]?.onClick) btn[propsKey].onClick({});
    }""")
    
    time.sleep(5)
    
    # Find game-core frame
    gc_frames = [f for f in page.frames if 'game-core' in f.url or 'game_core' in f.url]
    if gc_frames:
        gc = gc_frames[0]
        print(f"  Game-core: {gc.url[:250]}", flush=True)
        
        # Extract game-core state
        print("\n[4] Analyzing game-core...", flush=True)
        state = gc.evaluate("""() => ({
            bodyLen: document.body?.innerHTML?.length || 0,
            url: location.href,
            title: document.title,
            scripts: Array.from(document.scripts).map(s => s.src.substring(0, 150) || s.id).join(', '),
        })""")
        print(f"  State: {json.dumps(state)[:800]}", flush=True)
        
        # Check for canvas or game assets
        print("\n[5] Looking for captcha assets...", flush=True)
        assets = gc.evaluate("""() => ({
            imgs: Array.from(document.querySelectorAll('img')).map(i => i.src.substring(0, 200)).join(', '),
            canvases: document.querySelectorAll('canvas').length,
            divs: Array.from(document.querySelectorAll('div[id], div[class]')).slice(0, 20).map(d => d.id || d.className).join(', '),
        })""")
        print(f"  Assets: {json.dumps(assets)[:800]}", flush=True)
        
        # Check for FunCaptcha token
        print("\n[6] Looking for verification token...", flush=True)
        token_info = gc.evaluate("""() => {
            const vt = document.getElementById('verification-token');
            const fk = document.getElementById('funCaptcha-token');
            return {
                verificationToken: vt?.value?.substring(0, 200) || 'N/A',
                funCaptchaToken: fk?.value?.substring(0, 200) || 'N/A',
                funCaptcha: !!window.funCaptcha,
            };
        }""")
        print(f"  Tokens: {json.dumps(token_info)[:500]}", flush=True)
        
        page.screenshot(path="game_core_loaded.png")
        
    else:
        print("  No game-core frame found!", flush=True)
        # Check enforcement
        print(f"\n  Enforcement state:", flush=True)
        try:
            enf_state = enf.evaluate("""() => ({
                iframes: document.querySelectorAll('iframe').length,
                appLen: document.getElementById('app')?.innerHTML?.length || 0,
            })""")
            print(f"  {json.dumps(enf_state)}")
        except Exception as e:
            print(f"  Error: {e}")
    
    print(f"\n=== All frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(20)
    browser.close()
