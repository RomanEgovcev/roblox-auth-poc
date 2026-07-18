"""Check form validation and try direct API trigger."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Fill the form  
    page.fill("#login-username", USER)
    page.fill("#login-password", PASS)
    time.sleep(0.5)
    
    # Check form state and validation
    formInfo = page.evaluate("""() => {
        const username = document.querySelector('#login-username');
        const password = document.querySelector('#login-password');
        const loginBtn = document.querySelector('#login-button');
        
        // Check React fiber for disabled state
        const fiberKey = Object.keys(loginBtn).find(k => k.startsWith('__reactFiber'));
        const fiber = loginBtn[fiberKey];
        
        // Check if button is disabled
        return {
            usernameValue: username?.value,
            passwordValue: password?.value,
            buttonDisabled: loginBtn?.disabled,
            buttonClass: loginBtn?.className,
            buttonTabIndex: loginBtn?.tabIndex,
            fiberTag: fiber?.tag,
            fiberMemoizedProps: JSON.stringify(fiber?.memoizedProps)?.substring(0, 500),
            form: document.querySelector('form')?.outerHTML?.substring(0, 500),
            formOnSubmit: document.querySelector('form')?.getAttribute('onsubmit'),
        };
    }""")
    print(f"Form info:", flush=True)
    for k, v in formInfo.items():
        print(f"  {k}: {v}", flush=True)
    
    # Check if there are validation errors
    validation = page.evaluate("""() => {
        const els = document.querySelectorAll('[class*="error"], [class*="alert"], [class*="warning"], [role="alert"]');
        return Array.from(els).map(e => ({
            text: e.textContent?.trim()?.substring(0, 100),
            className: e.className?.substring(0, 100),
            id: e.id,
        }));
    }""")
    print(f"\nValidation/alerts on page:", flush=True)
    for v in validation:
        print(f"  {v['text']} (class={v['className']})", flush=True)
    
    # Try to force click the button by dispatching a click event
    triggerResult = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        if (!btn) return 'no button';
        
        // Try various click methods
        const results = [];
        
        // Method 1: Native click
        try {
            btn.click();
            results.push('native click: done');
        } catch(e) {
            results.push('native click error: ' + e.message);
        }
        
        // Check if any network request was made
        return results;
    }""")
    print(f"\nTrigger result: {triggerResult}", flush=True)
    
    # Check if React actually handles the click
    time.sleep(1)
    clickHandled = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        if (!fiberKey) return 'no fiber';
        
        let fiber = btn[fiberKey];
        // Walk up to find the component with onClick handler
        let depth = 0;
        while (fiber && depth < 10) {
            const props = fiber.memoizedProps || {};
            const handler = props.onClick || props.onMouseDown || props.onPointerDown;
            if (handler) {
                return {
                    depth,
                    handlerType: typeof handler,
                    handlerStr: handler.toString()?.substring(0, 300),
                    tag: fiber.tag,
                    type: fiber.type?.toString()?.substring(0, 200),
                };
            }
            fiber = fiber.return;
            depth++;
        }
        return 'no onClick handler found in fiber tree';
    }""")
    print(f"\nClick handler: {clickHandled}", flush=True)
    
    time.sleep(2)
    browser.close()
