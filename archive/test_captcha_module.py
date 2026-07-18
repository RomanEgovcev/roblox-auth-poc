"""Analyze Roblox Captcha.js and CaptchaCore.js modules."""
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
    
    # Find all Captcha script tags
    scripts = page.evaluate("""() => {
        const scripts = document.querySelectorAll('script');
        return Array.from(scripts).map(s => ({
            src: s.src,
            id: s.id,
            text_len: (s.textContent || '').length,
        })).filter(s => s.src.includes('Captcha') || s.text_len > 1000);
    }""")
    print(f"Captcha scripts:", flush=True)
    for s in scripts:
        print(f"  {json.dumps(s, indent=2)[:200]}", flush=True)
    
    # Look for the Captcha module in the page's global scope
    captcha_funcs = page.evaluate("""() => {
        const found = {};
        
        // Search all window properties
        for (const k of Object.keys(window)) {
            if (k.toLowerCase().includes('captcha') || k.toLowerCase().includes('funcapt')) {
                try {
                    const v = window[k];
                    if (typeof v === 'function') {
                        found[k + '()'] = v.toString().substring(0, 200);
                    } else {
                        found[k] = typeof v;
                    }
                } catch(e) {}
            }
        }
        
        // Check require if available
        if (typeof require === 'function') {
            try {
                const captchaModule = require('RobloxCaptcha');
                found['RobloxCaptcha (require)'] = Object.keys(captchaModule).slice(0, 20);
            } catch(e) {
                found['require captcha error'] = e.message;
            }
        }
        
        // Check for Roblox game loader / CoreScripts
        if (window.Roblox && window.Roblox.Captcha) {
            found.RobloxCaptcha = Object.keys(window.Roblox.Captcha).slice(0, 20);
        }
        
        return found;
    }""")
    print(f"\nCaptcha functions:", flush=True)
    print(json.dumps(captcha_funcs, indent=2)[:2000], flush=True)
    
    # Check Roblox namespace
    roblox_ns = page.evaluate("""() => {
        const info = {};
        if (window.Roblox) {
            info.Roblox_keys = Object.keys(window.Roblox).slice(0, 30);
        }
        return info;
    }""")
    print(f"\nRoblox namespace:", flush=True)
    print(json.dumps(roblox_ns, indent=2)[:500], flush=True)
    
    time.sleep(3)
    browser.close()
