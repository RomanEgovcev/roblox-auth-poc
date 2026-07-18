"""Check PX global functions and variables on page."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[40:100]}", flush=True) if 'collector' in r.url or 'px-cdn' in r.url or 'px-cloud' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Check PX-related globals
    px_globals = page.evaluate("""() => {
        const results = {};
        const keys = Object.keys(window).filter(k => 
            k.startsWith('_px') || 
            k.startsWith('PX') || 
            k.toLowerCase().includes('perimeter') ||
            k.toLowerCase().includes('px')
        );
        keys.forEach(k => {
            const v = window[k];
            results[k] = typeof v === 'function' ? 'function' : 
                typeof v === 'object' ? 'object(' + (v?.constructor?.name || 'unknown') + ')' : 
                typeof v === 'string' ? v.substring(0, 100) : 
                typeof v;
        });
        return results;
    }""")
    print(f"\nPX globals:", flush=True)
    for k, v in sorted(px_globals.items()):
        print(f"  {k}: {v}", flush=True)
    
    # Also check if px-cdn main.min.js exposes anything
    px_api = page.evaluate("""() => {
        // Look for PX challenge-related functions
        const funcs = [];
        for (const k of Object.getOwnPropertyNames(window)) {
            try {
                const v = window[k];
                if (typeof v === 'function' && k.toLowerCase().includes('px')) {
                    funcs.push(k);
                }
            } catch(e) {}
        }
        
        // Check _pxCaptcha
        if (typeof _pxCaptcha !== 'undefined') return { _pxCaptcha: typeof _pxCaptcha };
        if (typeof window._pxCaptcha !== 'undefined') return { _pxCaptcha: typeof _pxCaptcha };
        
        // Check for callback variables
        const scriptTags = document.querySelectorAll('script');
        const pxScripts = [];
        scriptTags.forEach(s => {
            if (s.src && (s.src.includes('px-cdn') || s.src.includes('px-cloud'))) {
                pxScripts.push(s.src.substring(0, 120));
            }
        });
        
        return { pxScripts };
    }""")
    print(f"\nPX API search:", flush=True)
    print(f"  {json.dumps(px_api, indent=2)[:500]}", flush=True)
    
    # Check if there's a PX object on any element
    px_elements = page.evaluate("""() => {
        const results = {};
        // Check document for PX-related attributes
        for (const attr of ['_px', 'px', 'data-px']) {
            const els = document.querySelectorAll(`[${attr}]`);
            if (els.length > 0) results[attr] = els.length;
        }
        return results;
    }""")
    print(f"\nPX elements: {json.dumps(px_elements) if px_elements else 'none'}", flush=True)
    
    time.sleep(2)
    browser.close()
