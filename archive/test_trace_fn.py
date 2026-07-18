"""Trace onFormSubmit execution to find why no API call."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    
    page.fill("#login-username", USER)
    page.fill("#login-password", PASS)
    time.sleep(0.5)
    
    # Monkey-patch qr, $e, etc. to see what's happening
    trace = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        let fiber = btn[fiberKey];
        for (let i = 0; i < 6 && fiber; i++) fiber = fiber.return;
        
        if (!fiber || fiber.tag !== 1) return {error: 'no class component'};
        
        const instance = fiber.stateNode;
        const props = instance.props;
        
        // Get the render method source to find $e and qr
        // Actually, $e and qr are probably in the closure of render
        // Let's look at the module that defines this component
        
        // Check if there are functions we can intercept globally
        // First, let's look at what fetch calls are made
        const originalFetch = window.fetch;
        window.__fetchCalls = [];
        window.fetch = function() {
            window.__fetchCalls.push({
                url: arguments[0],
                args: Array.from(arguments).map(a => typeof a === 'string' ? a.substring(0, 200) : JSON.stringify(a)?.substring(0, 200))
            });
            return originalFetch.apply(this, arguments);
        };
        
        // Also monitor XMLHttpRequest
        const origOpen = XMLHttpRequest.prototype.open;
        window.__xhrCalls = [];
        XMLHttpRequest.prototype.open = function() {
            window.__xhrCalls.push({method: arguments[0], url: arguments[1]?.substring(0, 200)});
            return origOpen.apply(this, arguments);
        };
        
        // Now call onFormSubmit
        try {
            const ret = props.onFormSubmit();
            return {
                called: true,
                returnType: typeof ret,
                fetchCalls: window.__fetchCalls,
                xhrCalls: window.__xhrCalls,
            };
        } catch(e) {
            return {error: e.message, stack: e.stack};
        } finally {
            window.fetch = originalFetch;
        }
    }""")
    
    print("Trace result:", flush=True)
    for k, v in trace.items():
        print(f"  {k}: {v}", flush=True)
    
    # Also check if loading state changed
    loadingCheck = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        let fiber = btn[fiberKey];
        for (let i = 0; i < 5 && fiber; i++) fiber = fiber.return;
        if (fiber && fiber.tag === 0) {
            // Check the component's props from the parent
            return {isLoading: fiber.memoizedProps?.isLoading};
        }
        return {error: 'no component'};
    }""")
    print(f"\nLoading state: {loadingCheck}", flush=True)
    
    time.sleep(3)
    browser.close()
