"""Find RobloxCaptcha module correctly."""
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
    
    # Find RobloxCaptcha module
    captcha_find = page.evaluate("""() => {
        const info = {};
        
        // Try direct access
        try { info.window_RobloxCaptcha = typeof window.RobloxCaptcha; } catch(e) {}
        try { info.RobloxCaptcha = typeof RobloxCaptcha; } catch(e) {}
        
        // Try require
        if (typeof require === 'function') {
            try {
                const m = require('RobloxCaptcha');
                info.require_RobloxCaptcha = Object.keys(m);
            } catch(e) {
                info.require_error = e.message;
            }
        }
        
        // Try Roblox.require
        if (window.Roblox && typeof window.Roblox.require === 'function') {
            try {
                const m = window.Roblox.require('RobloxCaptcha');
                info.Roblox_require_Captcha = Object.keys(m);
            } catch(e) {
                info.Roblox_require_error = e.message;
            }
        }
        
        // Search through Roblox
        if (window.Roblox) {
            info.Roblox_Captcha = window.Roblox.Captcha ? Object.keys(window.Roblox.Captcha).slice(0, 20) : 'not found';
            info.Roblox_RobloxCaptcha = window.Roblox.RobloxCaptcha ? Object.keys(window.Roblox.RobloxCaptcha).slice(0, 20) : 'not found';
            
            // Deep search
            for (const k of Object.keys(window.Roblox)) {
                try {
                    const v = window.Roblox[k];
                    if (typeof v === 'object' && v !== null) {
                        const keys = Object.keys(v);
                        if (keys.some(x => x.toLowerCase().includes('captcha'))) {
                            info['Roblox.' + k] = keys.slice(0, 20);
                        }
                    }
                } catch(e) {}
            }
        }
        
        return info;
    }""")
    
    print(f"RobloxCaptcha found:", flush=True)
    print(json.dumps(captcha_find, indent=2)[:2000], flush=True)
    
    # Try the likely path
    print(f"\n--- Trying Roblox.require('RobloxCaptcha') ---", flush=True)
    r = page.evaluate("""() => {
        try {
            const captcha = Roblox.require('RobloxCaptcha');
            if (captcha && typeof captcha.execute === 'function') {
                captcha.execute();
                return 'execute called';
            }
            return 'module found but no execute';
        } catch(e) {
            return 'error: ' + e.message;
        }
    }""")
    print(f"  {r}", flush=True)
    time.sleep(5)
    
    # Check for new frames
    print(f"\nFrames:", flush=True)
    for i, f in enumerate(page.frames):
        url = f.url
        if any(x in url for x in ['arkoselabs', 'enforcement', 'game-core', 'api.js']):
            print(f"  [{i}] {url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
