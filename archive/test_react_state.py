"""Check React's internal state for form values."""
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
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Fill form using page.fill
    page.fill('#login-username', USER)
    page.fill('#login-password', PASS)
    time.sleep(1)
    
    # Check DOM values and React state
    form_state = page.evaluate("""() => {
        const u = document.getElementById('login-username');
        const p = document.getElementById('login-password');
        
        // Get React fiber for each input
        function getFiberState(el) {
            if (!el) return null;
            const fiberKey = Object.keys(el).find(k => k.startsWith('__reactFiber'));
            if (!fiberKey) return {error: 'no fiber'};
            
            let fiber = el[fiberKey];
            // Walk up to find the form controller component
            let states = [];
            let depth = 0;
            while (fiber && depth < 30) {
                if (fiber.memoizedState) {
                    let queue = fiber.memoizedState;
                    let hookIndex = 0;
                    while (queue) {
                        if (queue.queue && queue.queue.lastRenderedState !== undefined) {
                            const val = queue.queue.lastRenderedState;
                            if (typeof val === 'string' || typeof val === 'boolean' || typeof val === 'number') {
                                states.push({depth, hookIndex, val: val.toString().substring(0, 40)});
                            }
                        }
                        queue = queue.next;
                        hookIndex++;
                    }
                }
                fiber = fiber.return;
                depth++;
            }
            return states;
        }
        
        const uFiber = getFiberState(u);
        const pFiber = getFiberState(p);
        
        return {
            domValues: {
                username: u ? u.value : 'N/A',
                password: p ? p.value : 'N/A',
            },
            uFiberState: uFiber,
            pFiberState: pFiber,
        };
    }""")
    
    print(f"Form state:", flush=True)
    print(json.dumps(form_state, indent=2)[:2000], flush=True)
    
    # Now try dispatching native input event as React expects it
    page.evaluate("""() => {
        const u = document.getElementById('login-username');
        const p = document.getElementById('login-password');
        if (u) {
            u.dispatchEvent(new Event('input', {bubbles: true}));
            u.dispatchEvent(new Event('change', {bubbles: true}));
        }
        if (p) {
            p.dispatchEvent(new Event('input', {bubbles: true}));
            p.dispatchEvent(new Event('change', {bubbles: true}));
        }
    }""")
    time.sleep(1)
    
    # Click and monitor
    click_time = time.time()
    page.click('.login-button', timeout=5000)
    print("\nClicked!", flush=True)
    
    time.sleep(5)
    
    # Check if API call was made
    auth_reqs = []
    page.on("request", lambda r: auth_reqs.append({"u": r.url[:150], "m": r.method, "t": time.time()}))
    # Re-scan old requests from page._context or just check final state
    
    print(f"Final URL: {page.url}", flush=True)
    
    time.sleep(2)
    browser.close()
