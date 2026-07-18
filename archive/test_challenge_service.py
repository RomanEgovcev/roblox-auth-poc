"""Explore Roblox.AccountIntegrityChallengeService and handle proofofwork challenge."""
import os, time, json, base64

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
    
    # Examine AccountIntegrityChallengeService
    aics = page.evaluate("""() => {
        const svc = window.Roblox?.AccountIntegrityChallengeService;
        if (!svc) return {error: 'no service'};
        
        const result = {};
        const keys = Object.keys(svc);
        result.keys = keys;
        
        keys.forEach(k => {
            if (typeof svc[k] === 'function') {
                result[k] = svc[k].toString().substring(0, 500);
            } else if (typeof svc[k] === 'object' && svc[k] !== null) {
                try { result[k] = JSON.stringify(svc[k]).substring(0, 300); } catch(e) { result[k] = 'object'; }
            } else {
                result[k] = String(svc[k]).substring(0, 100);
            }
        });
        
        return result;
    }""")
    print("=== AccountIntegrityChallengeService ===", flush=True)
    print(json.dumps(aics, indent=2)[:3000], flush=True)
    
    # Trigger PX challenge and capture headers
    csrf = page.evaluate("""async () => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
        });
        return r.headers.get('x-csrf-token');
    }""")
    
    # Full response with all headers
    response = page.evaluate("""async (csrf) => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json', 'x-csrf-token': csrf},
            body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
        });
        const headers = {};
        for (const [k, v] of r.headers.entries()) { headers[k] = v; }
        return {status: r.status, headers: headers, body: await r.text()};
    }""", csrf)
    
    if response['status'] == 403:
        meta_b64 = response['headers'].get('rblx-challenge-metadata', '')
        try:
            meta = json.loads(base64.b64decode(meta_b64).decode())
            print(f"\n=== Decoded challenge metadata ===", flush=True)
            print(json.dumps(meta, indent=2), flush=True)
        except:
            print(f"Could not decode metadata: {meta_b64[:100]}", flush=True)
        
        challenge_id = response['headers'].get('rblx-challenge-id', '')
        challenge_type = response['headers'].get('rblx-challenge-type', '')
        print(f"Challenge ID: {challenge_id}", flush=True)
        print(f"Challenge type: {challenge_type}", flush=True)
        
        # Now call the page's challenge service to handle this
        # The metadata says eligibleMethods is empty, so maybe this is just a blocking challenge
        # Let's try to call the challenge service's method
        print("\n[*] Trying to manually trigger challenge resolution...", flush=True)
        
        # Use Roblox.AccountIntegrityChallengeService or Roblox.Captcha
        result = page.evaluate("""(response) => {
            const svc = window.Roblox?.AccountIntegrityChallengeService;
            if (!svc) return 'no svc';
            
            // Try calling challenge methods
            const results = {};
            Object.keys(svc).forEach(k => {
                if (typeof svc[k] === 'function') {
                    try {
                        const ret = svc[k](response);
                        results[k] = 'called, returned: ' + String(ret).substring(0, 100);
                    } catch(e) {
                        results[k] = 'error: ' + (e.message || e).substring(0, 100);
                    }
                }
            });
            return results;
        }""", response)
        print(f"Challenge service calls: {json.dumps(result, indent=2)}", flush=True)
        
        # Also try calling Roblox.Captcha verify
        cap_result = page.evaluate("""(response) => {
            const cap = window.Roblox?.Captcha;
            if (!cap) return 'no cap';
            
            const results = {};
            Object.keys(cap).forEach(k => {
                if (typeof cap[k] === 'function') {
                    try {
                        const ret = cap[k]('login', response.body || '', () => {});
                        results[k] = 'called';
                    } catch(e) {
                        results[k] = 'error: ' + (e.message || e).substring(0, 100);
                    }
                }
            });
            return results;
        }""", response)
        print(f"Captcha calls: {json.dumps(cap_result, indent=2)}", flush=True)
    
    input("Enter...")
    browser.close()
