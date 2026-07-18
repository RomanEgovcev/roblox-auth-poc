"""Search for Arkose client API by checking the api.js response body."""
import os, time, json, re

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Intercept api.js response to see what object it creates
    api_js_content = {}
    def handle_response(r):
        if 'api.js' in r.url:
            r.text().then(lambda t: api_js_content.update({'body': t[:5000]}))
    page.on("response", handle_response)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Load api.js
    page.evaluate("""() => {
        return new Promise((resolve) => {
            const s = document.createElement('script');
            s.src = 'https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js';
            s.onload = () => setTimeout(resolve, 500);
            s.onerror = () => resolve();
            document.head.appendChild(s);
        });
    }""")
    time.sleep(1)
    
    print(f"[1] api.js first 5000 chars:", flush=True)
    body = api_js_content.get('body', '')
    print(f"  Length: {len(body)}", flush=True)
    print(f"  First 500: {body[:500]}", flush=True)
    print(f"  ...", flush=True)
    print(f"  Last 500: {body[-500:]}", flush=True)
    
    # Search for the variable name that api.js creates
    match = re.search(r'window\.(\w+)\s*=', body)
    if match:
        var_name = match.group(1)
        print(f"\n[2] Found variable: {var_name}", flush=True)
        
        # Check if it exists
        exists = page.evaluate(f"typeof window.{var_name}")
        print(f"  typeof: {exists}", flush=True)
        
        if exists != 'undefined':
            info = page.evaluate(f"""() => {{
                const api = window.{var_name};
                const keys = Object.keys(api);
                const methods = {{}};
                for (const k of keys.slice(0, 30)) {{
                    methods[k] = typeof api[k];
                }}
                return {{keys, methods}};
            }}""")
            print(f"  API keys: {json.dumps(info, indent=2)[:800]}", flush=True)
    
    # Broader search: any suspicious API object on window
    print(f"\n[3] Searching window for any Arkose-related objects...", flush=True)
    suspects = page.evaluate("""() => {
        const results = {};
        const keys = Object.keys(window);
        const arkoseKeys = keys.filter(k => 
            k.toLowerCase().includes('arkose') || 
            k.toLowerCase().includes('funcaptcha') ||
            (k.startsWith('_') && k.length > 20) ||
            (k.startsWith('ark') && k.length > 10)
        );
        results.arkoseKeys = arkoseKeys;
        
        // Check each found key
        for (const k of arkoseKeys.slice(0, 10)) {
            const v = window[k];
            results[k] = {
                type: typeof v,
                keys: typeof v === 'object' && v ? Object.keys(v).slice(0, 10) : null,
            };
        }
        
        return results;
    }""")
    print(f"  {json.dumps(suspects, indent=2)[:800]}", flush=True)
    
    time.sleep(3)
    browser.close()
