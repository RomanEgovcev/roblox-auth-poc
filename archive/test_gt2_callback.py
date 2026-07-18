"""Get Arkose session token with proper gt2 JSONP callback."""
import os, time, json, re

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Call gt2 with callback parameter
    print("[1] gt2 API with callback...", flush=True)
    gt2 = page.evaluate("""async () => {
        try {
            // Try with callback param
            const resp = await fetch('https://arkoselabs.roblox.com/fc/gt2/public_key/476068BF-9607-4799-B53D-966BE98E2B81?callback=test123');
            const text = await resp.text();
            return {
                status: resp.status,
                type: resp.headers.get('content-type'),
                len: text.length,
                preview: text.substring(0, 800),
            };
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"  GT2: {json.dumps(gt2)[:800]}", flush=True)
    
    # Parse session token from response
    if gt2.get('status') == 200:
        text_raw = page.evaluate("""async () => {
            const resp = await fetch('https://arkoselabs.roblox.com/fc/gt2/public_key/476068BF-9607-4799-B53D-966BE98E2B81?callback=test123');
            return await resp.text();
        }""")
        print(f"\n  Raw: {text_raw[:1000]}", flush=True)
        
        match = re.match(r'^test123\((.+)\);?$', text_raw.strip())
        if match:
            data = json.loads(match.group(1))
            session_token = data.get('session_token')
            print(f"\n  Session token: {session_token}", flush=True)
    else:
        # Try POST
        print("\n  Trying POST...", flush=True)
        gt2 = page.evaluate("""async () => {
            try {
                const resp = await fetch('https://arkoselabs.roblox.com/fc/gt2/public_key/476068BF-9607-4799-B53D-966BE98E2B81', {
                    method: 'POST',
                });
                const text = await resp.text();
                return {status: resp.status, preview: text.substring(0, 500)};
            } catch(e) {
                return {error: e.message};
            }
        }""")
        print(f"  POST: {json.dumps(gt2)[:500]}", flush=True)
        
        # Try with all params from the previous successful run
        # From the enforcement URL hash: ...session_token...
        print("\n  Checking if we can call fc/gfct/...", flush=True)
        gfct = page.evaluate("""async () => {
            try {
                const resp = await fetch('https://arkoselabs.roblox.com/fc/gfct/', {
                    credentials: 'include'
                });
                const text = await resp.text();
                return {status: resp.status, preview: text.substring(0, 500)};
            } catch(e) {
                return {error: e.message};
            }
        }""")
        print(f"  GFCT: {json.dumps(gfct)[:500]}", flush=True)
    
    time.sleep(3)
    browser.close()
