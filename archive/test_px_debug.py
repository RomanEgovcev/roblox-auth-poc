"""Debug PX state, eligibleMethods, and challenge configuration."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[:200]}", flush=True) if 'px-cloud' in r.url or 'arkoselabs' in r.url or 'auth.roblox.com/v2/login' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Get PX's main.min.js text to search for eligibleMethods
    print("[1] Checking PX state...", flush=True)
    px_state = page.evaluate("""() => {
        const results = {};
        
        // Check PX global
        if (typeof PX !== 'undefined') {
            results.PX_keys = Object.keys(PX);
            results.PX_Events_keys = typeof PX.Events !== 'undefined' ? Object.keys(PX.Events) : [];
            results.PX_ClientUuid = PX.ClientUuid?.substring(0, 30) || null;
            results.PX_setChallenge = typeof PX.setChallenge;
        } else {
            results.PX_error = 'PX not found';
        }
        
        // Check window.triggerCaptcha
        results.triggerCaptcha = typeof window.triggerCaptcha;
        if (typeof window.triggerCaptcha === 'function') {
            results.triggerCaptcha_str = window.triggerCaptcha.toString().substring(0, 100);
        }
        
        // Try to find eligibleMethods in the page scope
        try {
            results.eligibleMethods = typeof eligibleMethods !== 'undefined' ? eligibleMethods : 'undefined';
        } catch(e) {
            results.eligibleMethods_error = e.message;
        }
        
        return results;
    }""")
    print(f"  {json.dumps(px_state, indent=2)}", flush=True)
    
    # Now try to access PX internals
    print("\n[2] Looking at PX main.min.js internals...", flush=True)
    internals = page.evaluate("""() => {
        const results = {};
        
        // Check for PX internal service objects
        if (typeof PX !== 'undefined') {
            // List all own property names of PX
            results.PX_ownProps = Object.getOwnPropertyNames(PX);
            
            // Try to find the service object S
            results.S_from_window = typeof window.S;
            
            // Check for any global variables that look like PX internals
            const suspicious = [];
            for (let i = 0; i < 10; i++) {
                const key = String.fromCharCode(65 + i); // A, B, C, ...
                try {
                    const val = window[key];
                    if (typeof val === 'function' || (typeof val === 'object' && val !== null)) {
                        const str = String(val).substring(0, 100);
                        if (str.includes('captcha') || str.includes('challenge') || str.includes('PX')) {
                            suspicious.push({key, str});
                        }
                    }
                } catch(e) {}
            }
            results.suspicious = suspicious;
        }
        
        return results;
    }""")
    print(f"  {json.dumps(internals, indent=2)}", flush=True)
    
    # Check if we can find the PX service by searching through all script contexts
    print("\n[3] Searching registered scripts that might reveal PX config...", flush=True)
    scripts_info = page.evaluate("""() => {
        const scripts = document.querySelectorAll('script');
        return Array.from(scripts).slice(0, 5).map(s => ({
            id: s.id,
            src: s.src?.substring(0, 100) || '',
            type: s.type,
            textLen: s.textContent.length,
            textPreview: s.textContent.substring(0, 200),
        }));
    }""")
    print(f"  Scripts: {json.dumps(scripts_info, indent=2)[:600]}", flush=True)
    
    # Fill and try to submit
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    print("\n[4] Triggering React onClick...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        if (btn) {
            const pk = Object.keys(btn).find(k => k.startsWith('__reactProps'));
            btn[pk].onClick({});
        }
    }""")
    
    # Check auth responses
    print("\n[5] Monitoring for Arkose APIs...", flush=True)
    for i in range(40):
        for f in page.frames:
            if 'arkoselabs' in f.url:
                print(f"  [+] Frame at {i*0.5:.0f}s: {f.url[:120]}", flush=True)
                break
        time.sleep(0.5)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
