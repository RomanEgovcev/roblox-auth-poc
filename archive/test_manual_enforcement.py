"""Manually create enforcement by defining setupEnforcement0 and loading Arkose API."""
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
    
    # Get CSRF and trigger PX challenge
    csrf = page.evaluate("""async () => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
        });
        return r.headers.get('x-csrf-token');
    }""")
    
    result = page.evaluate("""async (csrf) => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json', 'x-csrf-token': csrf},
            body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
        });
        return {status: r.status, body: await r.text()};
    }""", csrf)
    print(f"Challenge: {result['status']}", flush=True)
    
    # Define setupEnforcement0 and load Arkose API
    print("[*] Defining setupEnforcement0 and loading Arkose API...", flush=True)
    page.evaluate("""() => {
        // Define the callback that Arkose API expects
        window.setupEnforcement0 = function(e, t) {
            console.log('setupEnforcement0 called', e, t);
            // The API should call this with (publicKey, options)
            // We'll create the enforcement iframe
            if (typeof e === 'string') {
                window.__arkosePublicKey = e;
                window.__arkoseSessionToken = t?.sessionToken || 'manual';
                console.log('Arkose public key:', e, 'token:', window.__arkoseSessionToken);
            }
        };
        
        // Create challenge container (needed by Arkose)
        const container = document.createElement('div');
        container.id = 'generic-challenge-container-proofofwork';
        container.innerHTML = '<div class="challenge-captcha-body"><div id="arkose-0"></div></div>';
        container.setAttribute('aria-hidden', 'true');
        document.body.appendChild(container);
        
        // Load Arkose API
        const script = document.createElement('script');
        script.src = 'https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js';
        script.setAttribute('data-callback', 'setupEnforcement0');
        script.async = true;
        script.defer = true;
        document.body.appendChild(script);
        
        console.log('Setup complete');
    }""")
    
    # Wait for Arkose to load
    print("[*] Waiting for Arkose...", flush=True)
    for i in range(30):
        frames_info = page.frames
        game = [f for f in frames_info if 'game-core' in f.url or 'arkoselabs.roblox.com' in f.url]
        enf = [f for f in frames_info if 'enforcement' in f.url]
        if i % 5 == 0:
            print(f"[{i}s] frames:{len(frames_info)} enf:{len(enf)} game:{len(game)}", flush=True)
            # Check if setupEnforcement was called
            has_key = page.evaluate("() => !!window.__arkosePublicKey")
            print(f"  arkose key set: {has_key}", flush=True)
        if game:
            print(f"[++] GAME-CORE: {game[0].url[:150]}", flush=True)
            break
        time.sleep(1)
    else:
        print("[-] No game-core", flush=True)
        # Check what happened
        state = page.evaluate("""() => {
            const scripts = Array.from(document.scripts).map(s => ({id: s.id, src: (s.src || '').substring(0, 150)}));
            const arkoseScript = scripts.find(s => s.src.includes('arkoselabs'));
            return {
                scripts: scripts.filter(s => s.src.includes('arkose')),
                setupEnforcement0_type: typeof window.setupEnforcement0,
                container: !!document.getElementById('generic-challenge-container-proofofwork'),
                frames: Array.from(document.querySelectorAll('iframe')).map(f => f.src.substring(0, 200))
            };
        }""")
        print(f"  State: {json.dumps(state, indent=2)}", flush=True)
    
    input("Enter...")
    browser.close()
