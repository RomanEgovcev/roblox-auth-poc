"""Check PX object and try different trigger methods."""
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
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    print("[1] Page loaded, waiting 5s...", flush=True)
    time.sleep(5)
    
    # Check PX details
    px_detail = page.evaluate("""() => {
        if (typeof PX === 'undefined') return {error: 'PX not found'};
        const keys = Object.keys(PX);
        const proto = Object.getOwnPropertyNames(Object.getPrototypeOf(PX));
        return {
            type: typeof PX,
            keys: keys.slice(0, 30),
            protoMethods: proto.slice(0, 20),
        };
    }""")
    print(f"\n  PX: {json.dumps(px_detail)[:500]}", flush=True)
    
    # Check if Challenge middleware exists
    middleware = page.evaluate("""() => {
        const result = {};
        // Try various ways Challenge.js might be accessed
        try { result.genericChallengeMiddlewareType = typeof genericChallengeMiddlewareType; } catch(e) {}
        try { result.PX_setChallenge = typeof PX.setChallenge; } catch(e) {}
        try { result.PX_genericChallenge = typeof PX.genericChallenge; } catch(e) {}
        try { result.oC = typeof oC; } catch(e) {}
        try { 
            // Check the #chef-boy-ardee script
            const script = document.getElementById('chef-boy-ardee');
            if (script) {
                result.scriptLen = (script.text || '').length;
                result.scriptId = script.id;
            }
        } catch(e) {}
        return result;
    }""")
    print(f"\n  Middleware: {json.dumps(middleware)}", flush=True)
    
    # Try to find Challenge.js - check for PX.setChallenge
    has_setChallenge = page.evaluate("""() => typeof PX !== 'undefined' && typeof PX.setChallenge !== 'undefined'""")
    print(f"\n  PX.setChallenge exists: {has_setChallenge}", flush=True)
    
    # Check chef-boy-ardee script for Challenge.js
    if middleware.get('scriptLen', 0) > 0:
        print(f"\n  chef-boy-ardee has content ({middleware['scriptLen']} chars)", flush=True)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    
    # Now try to trigger enforcement with Enter on various elements
    print("\n[2] Trying various trigger methods...", flush=True)
    
    enf_found = [False]
    def check_frames(frame):
        if 'arkoselabs.roblox.com' in frame.url and 'enforcement.' in frame.url:
            enf_found[0] = True
            print(f"  [+] Enforcement FOUND: {frame.url[:200]}", flush=True)
    
    page.on("frameattached", check_frames)
    page.on("framenavigated", check_frames)
    
    # Method 1: Click the login button with page.click
    print("  Method 1: page.click('#login-button')...", flush=True)
    try:
        page.click("#login-button", timeout=3000)
    except:
        print("    FAILED (timeout or CSP)", flush=True)
    time.sleep(5)
    
    if not enf_found[0]:
        # Method 2: dispatchEvent on password field
        print("  Method 2: dispatchEvent Enter on password...", flush=True)
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
        time.sleep(8)
    
    if not enf_found[0]:
        # Method 3: dispatchEvent on login button
        print("  Method 3: dispatchEvent click on login button...", flush=True)
        page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            if (!btn) return;
            btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
        }""")
        time.sleep(8)
    
    if not enf_found[0]:
        # Method 4: keyboard press Enter
        print("  Method 4: page.keyboard.press('Enter')...", flush=True)
        page.keyboard.press("Enter")
        time.sleep(8)
    
    if not enf_found[0]:
        # Method 5: Focus the button and press Enter
        print("  Method 5: Tab to button + Enter...", flush=True)
        page.keyboard.press("Tab")
        time.sleep(1)
        page.keyboard.press("Enter")
        time.sleep(8)
    
    if not enf_found[0]:
        # Method 6: Dispatch mousedown + mouseup + click
        print("  Method 6: Dispatch mousedown/up/click on button...", flush=True)
        page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            if (!btn) return;
            btn.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
            btn.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
            btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
        }""")
        time.sleep(8)
    
    print(f"\n  Final result: enf_found={enf_found[0]}", flush=True)
    
    print(f"\n=== Frames ({len(page.frames)}) ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    browser.close()
