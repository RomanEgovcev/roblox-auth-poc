"""Load api.js and initialize Arkose enforcement on the page."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[:200]}", flush=True) if 'arkoselabs' in r.url or 'auth.roblox.com/v2/login' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Load api.js dynamically
    print("[1] Loading Arkose api.js...", flush=True)
    page.evaluate("""() => {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js';
            script.onload = () => {
                console.log('api.js loaded');
                resolve(true);
            };
            script.onerror = () => reject(new Error('Failed to load api.js'));
            document.head.appendChild(script);
        });
    }""")
    print("  api.js loaded!", flush=True)
    time.sleep(2)
    
    # Check what api.js exposed
    print("\n[2] Checking Arkose globals...", flush=True)
    globals = page.evaluate("""() => {
        const arkoseKeys = Object.keys(window).filter(k => 
            k.toLowerCase().includes('arkose') || 
            k.toLowerCase().includes('funcaptcha') || 
            k.startsWith('Ark') ||
            k === '_ac' ||
            k === 'Arkose'
        );
        return {
            arkoseKeys: arkoseKeys.slice(0, 20),
            typeof_Arkose: typeof window.Arkose,
            typeof_ac: typeof window._ac,
        };
    }""")
    print(f"  {json.dumps(globals, indent=2)}", flush=True)
    
    # If _ac exists, try to initialize enforcement
    if globals.get('typeof_ac') == 'undefined':
        print("  _ac not found. Checking for other initialization patterns...", flush=True)
        
        # Check what was set on window by api.js
        window_diff = page.evaluate("""() => {
            const after = Object.keys(window).filter(k => {
                const v = window[k];
                return v !== null && v !== undefined && (typeof v === 'object' || typeof v === 'function');
            });
            // Look for anything related to challenge
            const challengeRelated = after.filter(k => {
                const v = window[k];
                const s = String(v).substring(0, 200);
                return s.includes('challenge') || s.includes('funcaptcha') || s.includes('arkose');
            });
            return {
                challengeRelated: challengeRelated.slice(0, 20),
            };
        }""")
        print(f"  {json.dumps(window_diff, indent=2)[:400]}", flush=True)
    
    # Check if there's an Arkose iframe already
    print(f"\n[3] Frames:", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(5)
    browser.close()
