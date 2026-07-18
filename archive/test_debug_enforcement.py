"""Debugging: What triggers enforcement on the page?"""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Log key responses
    all_resp = []
    def log_resp(r):
        all_resp.append({'t': f"{time.time():.0f}", 's': r.status, 'u': r.url[:200]})
    page.on("response", log_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Register listener for frames so we don't miss enforcement
    created_frames = []
    page.on("frameattached", lambda f: created_frames.append({'type': 'attached', 'url': f.url[:200], 't': time.time()}))
    page.on("framenavigated", lambda f: created_frames.append({'type': 'navigated', 'url': f.url[:200], 't': time.time()}))
    
    # Check PX state
    print("[1] Page state at t=3s...", flush=True)
    state = page.evaluate("""() => ({
        hasPX: typeof PX !== 'undefined',
        hasTriggerCaptcha: typeof window.triggerCaptcha !== 'undefined',
        triggerCaptchaType: typeof window.triggerCaptcha,
        hasForm: !!document.getElementById('login-form'),
        hasButton: !!document.getElementById('login-button'),
        formAction: document.getElementById('login-form')?.action || 'N/A',
        formMethod: document.getElementById('login-form')?.method || 'N/A',
        framesCount: document.querySelectorAll('iframe').length,
        frameSrcs: Array.from(document.querySelectorAll('iframe')).slice(0, 5).map(f => f.src.substring(0, 200)),
    })""")
    print(f"  {json.dumps(state, indent=2)}", flush=True)
    
    # Check recent responses for auth 403
    print(f"\n[2] Recent responses...", flush=True)
    for r in all_resp[-10:]:
        print(f"  [t={r['t']}s {r['s']}] {r['u']}", flush=True)
    
    # Try different trigger methods
    print(f"\n[3] Testing dispatchEvent click...", flush=True)
    page.evaluate("""(() => {
        const btn = document.getElementById('login-button');
        if (!btn) return;
        // Try DispatchedEvent on button
        btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
    })()""")
    time.sleep(5)
    
    # Check if enforcement appeared
    print(f"  Frames:", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"    [{fi}] {f.url[:200]}", flush=True)
    
    print(f"\n  Frame events: {json.dumps(created_frames[-5:])}", flush=True)
    
    # Try window.triggerCaptcha directly
    print(f"\n[4] Checking if triggerCaptcha is available...", flush=True)
    tc = page.evaluate("""() => ({
        hasTC: typeof window.triggerCaptcha !== 'undefined',
        tcStr: typeof window.triggerCaptcha === 'function' ? window.triggerCaptcha.toString().substring(0, 200) : 'N/A',
    })""")
    print(f"  triggerCaptcha: {json.dumps(tc)[:300]}", flush=True)
    
    # If triggerCaptcha exists, call it
    if tc.get('hasTC'):
        print(f"  Calling triggerCaptcha...", flush=True)
        page.evaluate("window.triggerCaptcha()")
        time.sleep(5)
        for fi, f in enumerate(page.frames):
            if 'arkoselabs' in f.url:
                print(f"    [+] {f.url[:200]}", flush=True)
    
    # Check if there's a PX auto-trigger
    print(f"\n[5] Checking PX auto-trigger...", flush=True)
    px_state = page.evaluate("""() => {
        if (typeof PX === 'undefined') return {error: 'No PX'};
        const keys = Object.keys(PX);
        return {
            keys,
            hasEvents: typeof PX.Events !== 'undefined',
            eventsKeys: typeof PX.Events !== 'undefined' ? Object.keys(PX.Events) : [],
            hasSetChallenge: typeof PX.setChallenge !== 'undefined',
            setChallengeStr: typeof PX.setChallenge === 'function' ? PX.setChallenge.toString().substring(0, 100) : 'N/A',
        };
    }""")
    print(f"  {json.dumps(px_state, indent=2)}", flush=True)
    
    # Wait longer and check repeatedly
    print(f"\n[6] Waiting 30s for enforcement...", flush=True)
    for i in range(60):
        for f in page.frames:
            if 'arkoselabs' in f.url and 'enforcement.' in f.url:
                print(f"  [+] Enforcement at t={i*0.5:.0f}s!", flush=True)
                print(f"      {f.url[:200]}", flush=True)
                break
        time.sleep(0.5)
    
    print(f"\n=== All responses ===", flush=True)
    for r in all_resp:
        print(f"  [t={r['t']}s {r['s']}] {r['u']}", flush=True)
    
    time.sleep(5)
    browser.close()
