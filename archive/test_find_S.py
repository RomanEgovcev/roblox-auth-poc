"""Find the S object and explore Captcha module."""
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
    
    # Find the S variable (search for all S-like references in closure)
    s_info = page.evaluate("""() => {
        const info = {};
        
        // Try to find where triggerCaptcha is defined
        // Look at the ReactLogin.js bundle for captcha-related code
        // Check if there's a global S object (not the string 'S')
        
        // Search other global references
        for (const k of Object.keys(window)) {
            if (k.length === 1 && k >= 'A' && k <= 'Z') {
                try {
                    const v = window[k];
                    if (typeof v === 'object' && v !== null) {
                        const keys = Object.getOwnPropertyNames(v).slice(0, 10);
                        if (keys.includes('triggerCaptcha') || keys.some(x => x.includes('aptcha'))) {
                            info[k] = {
                                type: typeof v,
                                keys: keys.slice(0, 15),
                            };
                        }
                    }
                } catch(e) {}
            }
        }
        
        // Check React components / __reactFiber
        const root = document.getElementById('react-root') || document.querySelector('#login-container');
        if (root) {
            const keys = Object.keys(root);
            info.root_keys = keys.filter(k => k.startsWith('__react')).slice(0, 10);
        }
        
        return info;
    }""")
    print(f"S search:", flush=True)
    print(json.dumps(s_info, indent=2)[:1000], flush=True)
    
    # Check React login component state - look for captcha tokens
    react_state = page.evaluate("""() => {
        const info = {};
        
        // Try to find React fiber
        const root = document.getElementById('react-root');
        if (!root) {
            // Try other common React root elements
            const allDivs = document.querySelectorAll('div');
            for (const div of allDivs) {
                const keys = Object.keys(div).filter(k => k.startsWith('__react'));
                if (keys.length > 0) {
                    info.react_keys = keys;
                    // Check first key
                    const fiber = div[keys[0]];
                    if (fiber) {
                        const fKeys = Object.keys(fiber).slice(0, 20);
                        info.fiber_keys = fKeys;
                    }
                    break;
                }
            }
        }
        
        return info;
    }""")
    print(f"\nReact state:", flush=True)
    print(json.dumps(react_state, indent=2)[:1000], flush=True)
    
    # Check if there's a captcha token input field
    captcha_inputs = page.evaluate("""() => {
        const inputs = document.querySelectorAll('input[name=\"captchaToken\"], input[id*=\"captcha\"], input[data-testid*=\"captcha\"]');
        return Array.from(inputs).map(i => ({id: i.id, name: i.name, value: i.value.substring(0, 50)}));
    }""")
    print(f"\nCaptcha inputs:", flush=True)
    print(json.dumps(captcha_inputs, indent=2)[:500], flush=True)
    
    # Check RobloxCaptcha global
    roblox_captcha = page.evaluate("""() => {
        const info = {};
        
        // Check window.RobloxCaptcha
        if (window.RobloxCaptcha) info.RobloxCaptcha = Object.keys(window.RobloxCaptcha).slice(0, 20);
        
        // Check if Captcha is a require module
        // Look for require/module patterns
        if (window.require) info.has_require = true;
        
        return info;
    }""")
    print(f"\nCaptcha globals:", flush=True)
    print(json.dumps(roblox_captcha, indent=2)[:500], flush=True)
    
    time.sleep(3)
    browser.close()
