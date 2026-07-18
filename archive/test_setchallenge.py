"""Call PX.setChallenge to create enforcement after challenge."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Get CSRF and trigger challenge
    csrf = page.evaluate("""async () => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
        });
        return r.headers.get('x-csrf-token');
    }""")
    
    # Trigger PX
    result = page.evaluate("""async (csrf) => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json', 'x-csrf-token': csrf},
            body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
        });
        const text = await r.text();
        return {status: r.status, body: text};
    }""", csrf)
    print(f"Challenge: {result['status']}", flush=True)
    
    # Examine PX data
    px_data = page.evaluate("""() => {
        const px = window.PX;
        const result = {};
        
        // Look at PX internal state
        // Try to find challenge data
        const keys = Object.keys(px);
        keys.forEach(k => {
            if (typeof px[k] === 'function') {
                if (k === 'setChallenge') {
                    result.setChallenge_src = px[k].toString();
                }
            } else if (typeof px[k] === 'object' && px[k] !== null) {
                try {
                    result[k + '_json'] = JSON.stringify(px[k]).substring(0, 500);
                } catch(e) {
                    result[k + '_keys'] = Object.keys(px[k]).join(', ');
                }
            }
        });
        
        return result;
    }""")
    print(f"PX state: {json.dumps(px_data, indent=2)[:1000]}", flush=True)
    
    # Check what mC function needs. Try calling setChallenge with generic data
    print("\n[*] Trying PX.setChallenge with different data...", flush=True)
    
    # Try 1: with empty object
    try:
        result1 = page.evaluate("""() => {
            try {
                window.PX.setChallenge({});
                return 'called with {}';
            } catch(e) {return 'error: ' + e.message;}
        }""")
        print(f"  empty obj: {result1}", flush=True)
    except Exception as ex:
        print(f"  eval error: {ex}", flush=True)
    
    # Wait and check for frames
    time.sleep(3)
    
    # Check if frames appeared
    print(f"\nFrames after setChallenge: {[f.url[:100] for f in page.frames]}", flush=True)
    
    # Look at what events the page emits
    # Maybe we need to trigger the captcha via Roblox.FunCaptcha
    print("\n[*] Trying Roblox.FunCaptcha...", flush=True)
    fc_result = page.evaluate("""() => {
        const fc = window.Roblox?.FunCaptcha;
        if (!fc) return 'no fc';
        
        // Check captcha instances
        return {
            types: fc.types,
            captchaInstances: Object.keys(fc.captchaInstances || {}),
            methods: Object.keys(fc).filter(k => typeof fc[k] === 'function')
        };
    }""")
    print(f"  {json.dumps(fc_result, indent=2)}", flush=True)
    
    # Try calling showFunCaptchaInModal
    print("\n[*] Trying showFunCaptchaInModal...", flush=True)
    try:
        fc_show = page.evaluate("""() => {
            try {
                window.Roblox.FunCaptcha.showFunCaptchaInModal();
                return 'called';
            } catch(e) {return 'error: ' + (e.message || e);}
        }""")
        print(f"  {fc_show}", flush=True)
        time.sleep(3)
        print(f"  Frames: {[f.url[:100] for f in page.frames]}", flush=True)
    except Exception as ex:
        print(f"  eval error: {ex}", flush=True)
    
    input("Enter...")
    browser.close()
