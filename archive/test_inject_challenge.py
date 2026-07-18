"""Submit auth via requests with browser cookies, inject challenge to PX."""
import os, time, json, sys, re, requests

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
    
    enf_frames = []
    def track_frames(frame):
        if 'arkoselabs.roblox.com' in frame.url and 'enforcement.' in frame.url:
            enf_frames.append(frame)
            print(f"  [+] Enforcement: {frame.url[:200]}", flush=True)
    page.on("frameattached", track_frames)
    page.on("framenavigated", track_frames)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(8)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    
    # Pre-load enforcement via dispatchEvent click
    print("[1] Pre-loading enforcement via dispatchEvent click...", flush=True)
    page.evaluate("""() => {
        document.getElementById('login-button').dispatchEvent(
            new MouseEvent('click', {bubbles: true, cancelable: true, view: window})
        );
    }""")
    
    print("  Waiting 10s for enforcement...", flush=True)
    for i in range(20):
        if len(enf_frames) > 0:
            print(f"  Found at {i*0.5:.0f}s!", flush=True)
            break
        time.sleep(0.5)
    
    if not enf_frames:
        print("  Retrying...", flush=True)
        page.evaluate("""() => {
            document.getElementById('login-button').dispatchEvent(
                new MouseEvent('click', {bubbles: true, cancelable: true, view: window})
            );
        }""")
        time.sleep(10)
    
    if not enf_frames:
        print("  No enforcement. Exiting.", flush=True)
        browser.close()
        exit()
    
    enf = enf_frames[0]
    print(f"  Enforcement URL: {enf.url[:250]}", flush=True)
    
    # Get CSRF token and browser cookies
    print("\n[2] Getting CSRF token and cookies...", flush=True)
    csrf = page.evaluate("""() => {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta?.getAttribute('data-token') || meta?.content || '';
    }""")
    print(f"  CSRF: {csrf[:50]}", flush=True)
    
    browser_cookies = page.context.cookies()
    cookies_dict = {c['name']: c['value'] for c in browser_cookies}
    print(f"  Cookies: {json.dumps(cookies_dict)[:200]}", flush=True)
    
    # Make auth request via Python requests with browser cookies
    print("\n[3] Submitting auth via Python requests...", flush=True)
    s = requests.Session()
    for name, value in cookies_dict.items():
        s.cookies.set(name, value, domain='.roblox.com')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Origin': 'https://www.roblox.com',
        'Referer': 'https://www.roblox.com/login',
        'X-CSRF-TOKEN': csrf,
    }
    
    r = s.post('https://www.roblox.com/v2/login', data={
        'username': USER,
        'password': PASS,
    }, headers=headers, timeout=15)
    
    print(f"  Status: {r.status_code}", flush=True)
    
    # Check for challenge headers
    challenge_data = {}
    for k, v in r.headers.items():
        if 'challenge' in k.lower() or 'rblx' in k.lower():
            challenge_data[k] = v
            print(f"  {k}: {v[:200]}", flush=True)
    
    print(f"  Body: {r.text[:300]}", flush=True)
    
    if r.status_code == 403 and challenge_data:
        print("\n[4] Got challenge! Injecting into PX...", flush=True)
        
        # Build challenge object from headers
        injection = page.evaluate(f"""() => {{
            const challengeData = {json.dumps(challenge_data)};
            
            // Build the same structure PX expects
            const t = {{
                challengeId: challengeData['rblx-challenge-id'] || '',
                challengeType: challengeData['rblx-challenge-type'] || '',
                challengeMetadata: challengeData['rblx-challenge-metadata'] || '',
            }};
            
            // Check current PX state
            const before = {{
                hasSetChallenge: typeof PX?.setChallenge === 'function',
                hasOC: typeof oC !== 'undefined',
            }};
            
            // Call setChallenge
            if (PX?.setChallenge) {{
                PX.setChallenge(t);
            }}
            
            const after = {{
                hasOC: typeof oC !== 'undefined',
                challengeId: t.challengeId?.substring(0, 50),
                challengeType: t.challengeType,
            }};
            
            return {{before, after}};
        }}""")
        
        print(f"  Injection result: {json.dumps(injection)[:500]}", flush=True)
        
        # Wait for game-core to load
        print("\n  Waiting 15s for game-core...", flush=True)
        time.sleep(15)
        
        # Check enforcement state
        try:
            enf_state = enf.evaluate("""() => ({
                iframes: document.querySelectorAll('iframe').length,
                appLen: document.getElementById('app')?.innerHTML?.length || 0,
                funCaptcha: !!window.funCaptcha,
                vt: document.getElementById('verification-token')?.value?.substring(0, 100) || 'N/A',
            })""")
            print(f"  Enforcement state: {json.dumps(enf_state)[:500]}", flush=True)
        except Exception as e:
            print(f"  Error reading enforcement: {e}", flush=True)
        
        print(f"\n  Final frames:", flush=True)
        for fi, f in enumerate(page.frames):
            print(f"    [{fi}] {f.url[:200]}", flush=True)
    
    else:
        print("\n  No challenge data received.", flush=True)
    
    page.screenshot(path="injected_challenge.png")
    time.sleep(5)
    browser.close()
