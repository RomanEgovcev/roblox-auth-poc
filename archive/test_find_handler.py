"""Find and invoke the React login handler directly."""
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
    time.sleep(10)
    
    page.fill("#login-username", USER)
    page.fill("#login-password", PASS)
    time.sleep(0.5)
    
    # Find the login button's React handler by walking up its fiber tree
    handler = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        if (!btn) return 'no button';
        
        // Get fiber key from button
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        if (!fiberKey) return 'no fiber on button';
        
        let fiber = btn[fiberKey];
        const results = [];
        let depth = 0;
        
        while (fiber && depth < 30) {
            const props = fiber.memoizedProps || {};
            const state = fiber.memoizedState;
            const type = fiber.type;
            const tag = fiber.tag;
            
            const entry = {
                depth,
                tag,
                typeName: typeof type === 'function' ? (type.name || 'anonymous') : String(type)?.substring(0, 80),
            };
            
            // Check for onClick handler
            if (props.onClick) {
                entry.onClickType = typeof props.onClick;
                entry.onClickStr = props.onClick.toString().substring(0, 500);
            }
            
            // Check state for username/password
            if (state && typeof state === 'object') {
                try {
                    // React hook state is a linked list
                    let hook = state;
                    while (hook) {
                        if (hook.queue && hook.memoizedState) {
                            const s = JSON.stringify(hook.memoizedState);
                            if (s && (s.includes('testuser') || s.includes('Username') || s.includes('password') || s.includes('ctype'))) {
                                entry.state = s.substring(0, 300);
                            }
                        }
                        hook = hook.next;
                    }
                } catch(e) {}
            }
            
            // Check pendingProps for form data
            if (fiber.pendingProps) {
                const pp = JSON.stringify(fiber.pendingProps);
                if (pp && pp.length < 2000 && (pp.includes('testuser') || pp.includes('Username') || pp.includes('password'))) {
                    entry.pendingProps = pp.substring(0, 300);
                }
            }
            
            // Also check memoizedProps for children with onClick
            if (props.children && typeof props.children === 'object') {
                const childStr = JSON.stringify(props.children)?.substring(0, 500);
                if (childStr && (childStr.includes('Log In') || childStr.includes('login'))) {
                    entry.childrenWithLogin = childStr;
                }
            }
            
            if (entry.onClickStr || entry.state || entry.pendingProps || entry.childrenWithLogin) {
                results.push(entry);
            }
            
            fiber = fiber.return;
            depth++;
        }
        
        return results;
    }""")
    
    print(f"Upward fiber walk:", flush=True)
    for h in handler:
        for k, v in h.items():
            print(f"  {k}: {v}", flush=True)
        print("---", flush=True)
    
    # Try to call the onClick handler directly
    clickResult = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        if (!btn) return 'no button';
        
        // Find React event handler props on the button
        const reactKey = Object.keys(btn).find(k => k.startsWith('__reactProps') || k.startsWith('__reactEventHandlers'));
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        
        const results = {buttonKeys: Object.keys(btn).filter(k => k.startsWith('__react'))};
        
        if (reactKey) {
            const props = btn[reactKey];
            results.reactPropsKeys = Object.keys(props);
            if (props.onClick) {
                results.onClickType = typeof props.onClick;
                results.onClickStr = props.onClick.toString().substring(0, 500);
                
                // Try calling it
                try {
                    const ret = props.onClick({type: 'click', target: btn, currentTarget: btn, preventDefault: () => {}, stopPropagation: () => {}});
                    results.onClickReturn = String(ret);
                } catch(e) {
                    results.onClickError = e.message;
                }
            }
        }
        
        // Also try to find the login function in the component
        // Look for the component at depth 5 (tag 0)
        if (fiberKey) {
            let fiber = btn[fiberKey];
            // Walk up 5 levels
            for (let i = 0; i < 5 && fiber; i++) fiber = fiber.return;
            
            if (fiber && fiber.tag === 0) {
                // Function component - try to find its hooks
                const hooks = fiber.memoizedState;
                if (hooks) {
                    results.hooksFound = true;
                    // Walk the hook linked list
                    let hook = hooks;
                    let idx = 0;
                    while (hook) {
                        if (hook.memoizedState && typeof hook.memoizedState === 'function') {
                            results['hook' + idx + '_fn'] = hook.memoizedState.toString().substring(0, 200);
                        } else if (hook.memoizedState && typeof hook.memoizedState === 'object') {
                            const s = JSON.stringify(hook.memoizedState);
                            if (s && s.length < 500) {
                                results['hook' + idx] = s;
                            }
                        }
                        hook = hook.next;
                        idx++;
                    }
                }
            }
        }
        
        return results;
    }""")
    
    print(f"\nClick handler analysis:", flush=True)
    for k, v in clickResult.items():
        print(f"  {k}: {v}", flush=True)
    
    time.sleep(2)
    browser.close()
