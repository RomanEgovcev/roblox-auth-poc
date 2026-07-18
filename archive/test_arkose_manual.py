"""Manual Arkose challenge creation by calling gt2 API directly."""
import os, time, json, urllib.request

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

PUBLIC_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"
ENFORCEMENT_HASH = "162a14c47922edcced45ca4d9b28e5d5"

# First, get a session token from the Arkose gt2 API
print("[1] Getting session token from Arkose gt2...", flush=True)

# We need to call the gt2 API, but it returns JSONP. Let me use urllib + proper cookies.
# First, get the cookies by visiting the Roblox login page
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    context = browser.new_context()
    page = context.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Get cookies from the browser
    cookies = context.cookies()
    cookie_header = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
    print(f"  Cookies count: {len(cookies)}", flush=True)
    
    # Call gt2 API from page context to get session token
    print("\n[2] Calling gt2 API...", flush=True)
    gt2_result = page.evaluate("""async () => {
        try {
            const resp = await fetch('https://arkoselabs.roblox.com/fc/gt2/public_key/476068BF-9607-4799-B53D-966BE98E2B81');
            const text = await resp.text();
            return {
                status: resp.status,
                len: text.length,
                preview: text.substring(0, 500),
            };
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"  GT2 result: {json.dumps(gt2_result)[:600]}", flush=True)
    
    # Try to get the session token from the gt2 response
    if gt2_result.get('status') == 200:
        gt2_text = page.evaluate("""async () => {
            const resp = await fetch('https://arkoselabs.roblox.com/fc/gt2/public_key/476068BF-9607-4799-B53D-966BE98E2B81');
            return await resp.text();
        }""")
        print(f"\n  Raw GT2: {gt2_text[:1000]}", flush=True)
        
        # Parse the JSONP response
        # The response format is: callback({...})
        import re
        match = re.match(r'^([\w.]+)\((.+)\);?$', gt2_text.strip())
        if match:
            callback_name = match.group(1)
            json_str = match.group(2)
            try:
                data = json.loads(json_str)
                session_token = data.get('session_token')
                print(f"\n  Session token: {session_token}", flush=True)
            except:
                print(f"  Could not parse JSON", flush=True)
        else:
            print(f"  Not JSONP format: {gt2_text[:200]}", flush=True)
    
    # Check if we can also call the settings API
    print("\n[3] Calling settings API...", flush=True)
    settings = page.evaluate("""async () => {
        try {
            const resp = await fetch('https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/settings');
            const text = await resp.text();
            return {
                status: resp.status,
                preview: text.substring(0, 500),
            };
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"  Settings: {json.dumps(settings)[:500]}", flush=True)
    
    # Also check api.js
    print("\n[4] Calling api.js...", flush=True)
    api_js = page.evaluate("""async () => {
        try {
            const resp = await fetch('https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js');
            const text = await resp.text();
            return {
                status: resp.status,
                len: text.length,
                preview: text.substring(0, 300),
            };
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"  API.js: {json.dumps(api_js)[:500]}", flush=True)
    
    time.sleep(3)
    browser.close()
