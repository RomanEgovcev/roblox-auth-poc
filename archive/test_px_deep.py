"""Deep dive into PX object properties."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    px_info = page.evaluate("""() => {
        const info = {};
        
        // PX object
        if (window.PX) {
            info.PX_type = typeof window.PX;
            info.PX_keys = Object.getOwnPropertyNames(window.PX).slice(0, 30);
            info.PX_proto = Object.getOwnPropertyNames(Object.getPrototypeOf(window.PX)).slice(0, 20);
            
            // Check if PX has specific methods
            const methods = {};
            for (const k of Object.getOwnPropertyNames(window.PX)) {
                try {
                    const v = window.PX[k];
                    if (typeof v === 'function') {
                        methods[k] = 'function(' + v.length + ' params)';
                    } else if (typeof v === 'object' && v !== null) {
                        methods[k] = 'object(' + (v.constructor?.name || '') + ')';
                    } else {
                        methods[k] = typeof v + ' = ' + String(v).substring(0, 100);
                    }
                } catch(e) {
                    methods[k] = 'error: ' + e.message;
                }
            }
            info.PX_methods = methods;
        }
        
        // PXbf8PROpW
        if (window.PXbf8PROpW) {
            info.PXinst_type = typeof window.PXbf8PROpW;
            const keys = Object.getOwnPropertyNames(window.PXbf8PROpW);
            info.PXinst_keys = keys.slice(0, 30);
            
            const methods = {};
            for (const k of keys) {
                try {
                    const v = window.PXbf8PROpW[k];
                    if (typeof v === 'function') {
                        methods[k] = 'function(' + v.length + ' params)';
                    } else if (typeof v === 'object' && v !== null) {
                        methods[k] = 'object(' + (v.constructor?.name || '') + ')';
                    } else {
                        methods[k] = typeof v + ' = ' + String(v).substring(0, 100);
                    }
                } catch(e) {
                    methods[k] = 'error: ' + e.message;
                }
            }
            info.PXinst_methods = methods;
        }
        
        return info;
    }""")
    
    print(f"PX objects:", flush=True)
    print(json.dumps(px_info, indent=2)[:3000], flush=True)
    
    # Also check PX.setChallenge
    has_set_challenge = page.evaluate("typeof PX.setChallenge === 'function'")
    print(f"\nPX.setChallenge: {has_set_challenge}", flush=True)
    
    time.sleep(2)
    browser.close()
