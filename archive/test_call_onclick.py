"""Download Challenge.js and find form submission logic."""
import os, time, json, sys, re

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Find the React handler f and call it
    print("=== Calling React onClick directly ===", flush=True)
    
    # First, find f by tracing the fiber
    f_trace = page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        
        // Go up the fiber tree to find the component that owns the onClick
        let fiber = btn[fiberKey];
        let depth = 0;
        while (fiber && depth < 30) {
            const props = fiber.memoizedProps;
            const state = fiber.memoizedState;
            
            // Check props for onClick
            if (props?.onClick) {
                const handlerStr = props.onClick.toString();
                return {
                    depth,
                    handler: handlerStr.substring(0, 200),
                    // Get the function's name and source
                    fiberTag: fiber.tag,
                    type: fiber.type?.toString().substring(0, 100) || 'unknown',
                };
            }
            
            // Check if this fiber has a stateNode with the handler
            // (class components have stateNode)
            if (fiber.stateNode && fiber.stateNode.clickHandler) {
                return {found: 'stateNode.clickHandler', depth};
            }
            
            fiber = fiber.return;
            depth++;
        }
        
        return {depth, fiberTag: fiber?.tag};
    }""")
    print(f"  {json.dumps(f_trace)[:500]}", flush=True)
    
    # Try to find S (the object with triggerCaptcha)
    print("\n=== Finding S (triggerCaptcha context) ===", flush=True)
    s_trace = page.evaluate("""() => {
        // Recursively search window for objects with triggerCaptcha
        const results = [];
        const visited = new Set();
        
        function search(obj, path, depth) {
            if (depth > 3) return;
            if (!obj || typeof obj !== 'object') return;
            if (visited.has(obj)) return;
            visited.add(obj);
            
            try {
                for (const key of Object.getOwnPropertyNames(obj).slice(0, 20)) {
                    try {
                        const val = obj[key];
                        if (key === 'triggerCaptcha' && typeof val === 'function') {
                            results.push({path: path, fnStr: val.toString().substring(0, 100)});
                        }
                        if (typeof val === 'object' && val !== null) {
                            search(val, path + '.' + key, depth + 1);
                        }
                    } catch(e) {}
                }
            } catch(e) {}
        }
        
        search(window, 'window', 0);
        return results;
    }""")
    print(f"  {json.dumps(s_trace)[:600]}", flush=True)
    
    # Call the React onClick handler directly with empty event
    print("\n=== Calling onClick handler ===", flush=True)
    result = page.evaluate("""async () => {
        try {
            const btn = document.getElementById('login-button');
            const propsKey = Object.keys(btn).find(k => k.startsWith('__reactProps'));
            if (!propsKey) return {error: 'no reactProps'};
            
            const props = btn[propsKey];
            if (!props?.onClick) return {error: 'no onClick'};
            
            const handler = props.onClick;
            // handler is function(e){return f()}
            // Call it with a dummy event
            const result = handler({});
            
            return {ok: true, resultType: typeof result, result: result};
        } catch(e) {
            return {error: e.message, stack: e.stack.substring(0, 200)};
        }
    }""")
    print(f"  Result: {json.dumps(result)[:500]}", flush=True)
    
    time.sleep(10)
    
    print(f"\n  URL: {page.url[:200]}", flush=True)
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    browser.close()
