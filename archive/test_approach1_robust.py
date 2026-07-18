"""Robust dispatchEvent + real session flow with fallbacks."""
import os, time, json, base64, sys

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    arkose_resp = []
    page.on("response", lambda r: arkose_resp.append(r) if 'arkoselabs.roblox.com' in r.url else None)
    
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)[:200]))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Check button state before
    btn_state = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        if (!btn) return 'no button';
        return {
            disabled: btn.disabled,
            tag: btn.tagName,
            classes: btn.className,
            rect: JSON.stringify(btn.getBoundingClientRect()),
            listeners: typeof getEventListeners === 'function' ? 'available' : 'not available'
        };
    }""")
    print(f"[*] Button state: {json.dumps(btn_state)}", flush=True)
    
    # ===== METHOD 1: dispatchEvent =====
    print("\n[1] dispatchEvent click...", flush=True)
    page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        if (btn) {
            btn.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
            btn.dispatchEvent(new PointerEvent('pointerup', {bubbles: true}));
            btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
        }
    }""")
    time.sleep(5)
    
    api_count = len(arkose_resp)
    print(f"  API calls: {api_count}", flush=True)
    for r in arkose_resp:
        print(f"    [{r.status}] {r.url[:150]}", flush=True)
    
    enf_frame = None
    for f in page.frames:
        if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
            enf_frame = f
            break
    
    if not enf_frame:
        # ===== METHOD 2: Press Enter =====
        print("\n[2] Press Enter...", flush=True)
        page.keyboard.press("Enter")
        time.sleep(5)
        
        new_count = len(arkose_resp)
        for i in range(new_count - api_count):
            r = arkose_resp[api_count + i]
            print(f"    [{r.status}] {r.url[:150]}", flush=True)
        
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                break
        
        if enf_frame:
            print(f"  [+] Found after Enter!", flush=True)
    
    if not enf_frame:
        # ===== METHOD 3: dispatchEvent on form =====
        print("\n[3] Submit form directly...", flush=True)
        page.evaluate("""() => {
            const form = document.querySelector('form');
            if (form) {
                const submitEvent = new SubmitEvent('submit', {bubbles: true, cancelable: true});
                form.dispatchEvent(submitEvent);
            }
        }""")
        time.sleep(5)
        
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                break
    
    if not enf_frame:
        # ===== METHOD 4: type Enter more forcefully =====
        print("\n[4] Force Enter on password field...", flush=True)
        page.fill("input[name='password']", "wrongpass123!")
        page.evaluate("""() => {
            const pw = document.querySelector('input[name=\"password\"]');
            if (pw) {
                pw.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
                pw.dispatchEvent(new KeyboardEvent('keypress', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
                pw.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
            }
        }""")
        time.sleep(5)
        
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                break
    
    if enf_frame:
        enf_url = enf_frame.url
        print(f"\n[+] ENFORCEMENT FOUND: {enf_url[:250]}", flush=True)
        
        # Extract session token
        if '#' in enf_url:
            hash_part = enf_url.split('#')[1]
            if '&' in hash_part:
                session_token = hash_part.split('&')[1]
                print(f"  Session token: {session_token[:50]}...", flush=True)
            else:
                session_token = ''
                print(f"  No session token in hash", flush=True)
        else:
            session_token = ''
            print(f"  No hash in URL", flush=True)
        
        # Wait for game-core
        print(f"\n[*] Waiting for game-core in enforcement (90s)...", flush=True)
        for i in range(180):
            try:
                state = enf_frame.evaluate("""() => ({
                    challenge: !!document.getElementById('challenge'),
                    funCaptcha: !!document.getElementById('FunCaptcha'),
                    iframes: document.querySelectorAll('iframe').length,
                    bodyLen: document.body?.innerHTML?.length || 0,
                    appHTML: document.getElementById('app')?.innerHTML?.substring(0, 200) || 'N/A',
                })""")
                
                if state['challenge'] or state['funCaptcha'] or state['iframes'] > 0:
                    print(f"[+] Game-core at {i*0.5:.0f}s!", flush=True)
                    print(f"  State: {json.dumps(state)}", flush=True)
                    
                    canvas = enf_frame.evaluate("""() => ({
                        canvases: document.querySelectorAll('canvas').length,
                        buttons: document.querySelectorAll('button').length,
                        images: document.querySelectorAll('img').length,
                    })""")
                    print(f"  Elements: {json.dumps(canvas)}", flush=True)
                    break
                    
            except Exception as e:
                if i % 30 == 0:
                    print(f"  [{i*0.5:.0f}s] Error: {e}", flush=True)
            
            if i % 30 == 0 and i > 0:
                print(f"  [{i*0.5:.0f}s] Still waiting...", flush=True)
            time.sleep(0.5)
        
        # Final state
        try:
            final = enf_frame.evaluate("""() => ({
                bodyLen: document.body?.innerHTML?.length || 0,
                appHTML: document.getElementById('app')?.innerHTML?.substring(0, 500) || 'N/A',
                iframes: document.querySelectorAll('iframe').length,
            })""")
            print(f"\nFinal enf state: {json.dumps(final)[:500]}", flush=True)
        except Exception as e:
            print(f"\nFinal enf error: {e}", flush=True)
    else:
        print(f"\n[-] No enforcement found after all methods", flush=True)
        dom = page.evaluate("""() => ({
            arkose0: document.getElementById('arkose-0') ? 'exists' : 'missing',
            challengeContainer: document.getElementById('generic-challenge-container-proofofwork') ? 'exists' : 'missing',
            scripts: document.querySelectorAll('script[id^=arkose-script]').length,
            errors: document.querySelector('.error')?.innerText || '',
        })""")
        print(f"DOM: {json.dumps(dom)}", flush=True)
    
    print(f"\n=== Arkose API calls ({len(arkose_resp)}) ===", flush=True)
    for r in arkose_resp:
        print(f"  [{r.status}] {r.url[:180]}", flush=True)
    
    print(f"\n=== Errors ===", flush=True)
    for e in errors:
        print(f"  {e}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:180]}", flush=True)
    
    page.screenshot(path="approach1_final.png")
    time.sleep(10)
    browser.close()
