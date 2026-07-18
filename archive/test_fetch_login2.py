"""Persistent approach: multiple dispatch attempts, with patience."""
import os, time, json, sys

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
    
    calls = []
    page.on("response", lambda r: calls.append(f"[{r.status}] {r.url[:200]}") 
             if ('arkoselabs.roblox.com' in r.url or 'funcaptcha.com' in r.url) else None)
    
    enf_frame = [None]
    def check_frame(frame):
        if 'arkoselabs.roblox.com' in frame.url and 'enforcement.' in frame.url:
            enf_frame[0] = frame
    page.on("frameattached", check_frame)
    page.on("framenavigated", check_frame)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=15000)
    
    # Wait for full page load including PX
    print("[1] Waiting for page + PX to settle (15s)...", flush=True)
    for i in range(30):
        px_ready = page.evaluate("""() => typeof _px !== 'undefined' || typeof window._px === 'object'""")
        if px_ready:
            print(f"  PX ready at {i*0.5:.0f}s!", flush=True)
            break
        time.sleep(0.5)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(3)
    
    # Try dispatchEvent Enter multiple times with patience
    print("[2] Triggering dispatchEvent Enter (up to 30s)...", flush=True)
    for attempt in range(6):
        if enf_frame[0]:
            print(f"  [+] Enforcement appeared at attempt {attempt+1}!", flush=True)
            break
        
        page.evaluate("""() => {
            const pw = document.querySelector('input[name="password"]');
            if (!pw) return;
            ['keydown','keypress','keyup'].forEach(evt => {
                pw.dispatchEvent(new KeyboardEvent(evt, {
                    key: 'Enter', code: 'Enter', keyCode: 13, which: 13,
                    bubbles: true, cancelable: true
                }));
            });
        }""")
        
        for i in range(10):
            if enf_frame[0]:
                break
            time.sleep(0.5)
        
        if not enf_frame[0]:
            print(f"  Attempt {attempt+1} failed, waiting 2s...", flush=True)
            time.sleep(2)
    
    if not enf_frame[0]:
        print("  [-] dispatchEvent failed, trying keyboard.press...", flush=True)
        page.keyboard.press("Enter")
        time.sleep(10)
        
        if not enf_frame[0]:
            print("  [-] Still no enforcement.", flush=True)
            
            # Try intercepting Arkose frames directly
            for f in page.frames:
                if 'arkoselabs.roblox.com' in f.url:
                    print(f"  Found Arkose frame: {f.url[:200]}", flush=True)
                    enf_frame[0] = f
                    break
    
    if not enf_frame[0]:
        print("  [-] Giving up on enforcement.", flush=True)
        browser.close()
        exit()
    
    print(f"\n  Enforcement URL: {enf_frame[0].url[:250]}", flush=True)
    
    # Check if it has session token (UUID in URL)
    import re
    st_match = re.search(r'&([0-9a-f\-]{36})$', enf_frame[0].url)
    if st_match:
        print(f"  Session token: {st_match.group(1)}", flush=True)
    else:
        print("  No session token in URL!", flush=True)
    
    # Extract form data + submit via fetch
    print("\n[3] Getting form data...", flush=True)
    form_data = page.evaluate("""() => {
        const form = document.querySelector('form');
        if (!form) return null;
        const fd = new FormData(form);
        const result = {};
        for (const [k, v] of fd.entries()) {
            result[k] = typeof v === 'string' ? v : '[file]';
        }
        return result;
    }""")
    print(f"  Form data: {json.dumps(form_data)[:300]}", flush=True)
    
    print("\n[4] Submitting login via fetch through PX...", flush=True)
    result = page.evaluate("""async () => {
        try {
            const form = document.querySelector('form');
            if (!form) return {error: 'no form'};
            const fd = new FormData(form);
            const resp = await fetch('/v2/login', {
                method: 'POST',
                body: fd,
                credentials: 'include'
            });
            const text = await resp.text();
            return {
                status: resp.status,
                headers: Array.from(resp.headers.entries()).slice(0, 20),
                text: text.substring(0, 500)
            };
        } catch(e) {
            return {error: e.message, stack: e.stack?.substring(0, 200)};
        }
    }""")
    print(f"  Login result: {json.dumps(result)[:600]}", flush=True)
    
    # Wait for game-core
    print("\n[5] Waiting for game-core (20s)...", flush=True)
    gc_found = [False]
    def check_gc(frame):
        if ('game-core' in frame.url or 'game_core' in frame.url) and not gc_found[0]:
            gc_found[0] = True
            print(f"  [+] Game-core: {frame.url[:250]}", flush=True)
    page.on("frameattached", check_gc)
    page.on("framenavigated", check_gc)
    
    for i in range(40):
        if gc_found[0]:
            break
        # Check enforcement state
        if enf_frame[0]:
            try:
                iframes = enf_frame[0].evaluate("document.querySelectorAll('iframe').length")
                if iframes > 0:
                    print(f"  [+] Enforcement iframes: {iframes}", flush=True)
                    gc_found[0] = True
                    break
            except:
                pass
        time.sleep(0.5)
    
    if not gc_found[0]:
        # Final check of enforcement
        if enf_frame[0]:
            try:
                state = enf_frame[0].evaluate("""() => ({
                    iframes: document.querySelectorAll('iframe').length,
                    appLen: document.getElementById('app')?.innerHTML?.length || 0,
                    funCaptcha: !!window.funCaptcha,
                    vt: document.getElementById('verification-token')?.value?.substring(0, 100) || 'N/A'
                })""")
                print(f"\n  Final enforcement state: {json.dumps(state)}", flush=True)
            except Exception as e:
                print(f"  Error: {e}", flush=True)
    
    print(f"\n=== All frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    print(f"\n=== Arkose API calls ({len(calls)}) ===", flush=True)
    for c in calls:
        print(f"  {c}", flush=True)
    
    browser.close()
