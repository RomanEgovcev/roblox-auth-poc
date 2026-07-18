"""Find f function and try to login with proper events."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    auth_reqs = []
    page.on("response", lambda r: auth_reqs.append({"url": r.url[:150], "status": r.status}) if 'auth.roblox' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Try to find f
    print("=== Finding f function ===", flush=True)
    f_info = page.evaluate("""() => {
        // f is in the closure of onClick. We need to trace through React internals.
        const btn = document.querySelector('#login-button');
        const reactKey = Object.keys(btn).find(k => k.startsWith('__reactProps'));
        const props = btn[reactKey];
        
        // The onClick is function(e){return f()}
        // We can try to get f from the fiber's memoizedState or other internal structures
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        if (!fiberKey) return {error: 'no fiber'};
        
        const fiber = btn[fiberKey];
        
        // Walk up to find the component that defines f
        let node = fiber;
        const results = [];
        let depth = 0;
        while (node && depth < 20) {
            const info = {depth, tag: node.tag, type: null};
            
            // Get component type (function name)
            if (node.type) {
                if (typeof node.type === 'function') info.type = node.type.name || 'anonymous';
                else if (typeof node.type === 'string') info.type = node.type;
                else if (node.type.$$typeof) info.type = 'forwardRef/memo';
                else info.type = typeof node.type;
            }
            
            // Check stateNode for methods
            if (node.stateNode && node.stateNode.__proto__) {
                const proto = node.stateNode.__proto__;
                const protoMethods = Object.getOwnPropertyNames(proto).filter(p => typeof proto[p] === 'function');
                if (protoMethods.length > 0) info.methods = protoMethods;
            }
            
            // Check memoizedState
            if (node.memoizedState && typeof node.memoizedState === 'object') {
                // Check for pending state that might contain callbacks
                const stateKeys = Object.keys(node.memoizedState).join(',').substring(0, 200);
                if (stateKeys) info.stateKeys = stateKeys;
            }
            
            results.push(info);
            node = node.return;
            depth++;
        }
        
        return results;
    }""")
    print(json.dumps(f_info, indent=2)[:3000], flush=True)
    
    # Method: Try to get the source of f by examining the fiber
    print("\n=== Trying to extract f source ===", flush=True)
    f_src = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        const reactKey = Object.keys(btn).find(k => k.startsWith('__reactProps'));
        const props = btn[reactKey];
        
        // Get the raw onClick string
        const src = props.onClick.toString();
        
        // Walk up the fiber to find where f is defined
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        const fiber = btn[fiberKey];
        
        // Try to find hooks state
        let state = fiber.memoizedState;
        const hookStates = [];
        let idx = 0;
        while (state && idx < 20) {
            if (state.queue) {
                try {
                    const qStr = JSON.stringify(state.queue, (k, v) => typeof v === 'function' ? v.toString().substring(0, 100) : v, 2);
                    hookStates.push({idx, queue: qStr.substring(0, 500)});
                } catch(e) {
                    hookStates.push({idx, queueError: e.message});
                }
            }
            state = state.next;
            idx++;
        }
        
        return {onClickSrc: src, hooks: hookStates};
    }""")
    print(json.dumps(f_src, indent=2)[:3000], flush=True)
    
    # Try: Actually click with Playwright's real action
    print("\n=== Real Playwright click ===", flush=True)
    try:
        page.locator("#login-button").click(timeout=5000)
        print("  page.locator.click() done", flush=True)
    except Exception as e:
        print(f"  locator.click failed: {e}", flush=True)
    
    time.sleep(3)
    print(f"Auth: {[(r['url'][:60], r['status']) for r in auth_reqs]}", flush=True)
    
    # Try: Submit the form directly with Playwright's keyboard
    if not auth_reqs:
        print("\n=== Keyboard Enter ===", flush=True)
        page.locator("input[name='password']").press("Enter")
        time.sleep(3)
        print(f"Auth: {[(r['url'][:60], r['status']) for r in auth_reqs]}", flush=True)
    
    # Try: Force form submit (bypass React)
    if not auth_reqs:
        print("\n=== Form submit via JS ===", flush=True)
        form = page.evaluate("""() => {
            const form = document.querySelector('form[name="loginForm"]');
            if (form) {
                form.submit();
                return 'submitted';
            }
            return 'no form';
        }""")
        print(f"  {form}", flush=True)
        time.sleep(3)
        print(f"URL: {page.url[:150]}", flush=True)
    
    # Try: Type password and tab
    if not auth_reqs:
        print("\n=== Tab+Enter ===", flush=True)
        page.locator("input[name='password']").press("Tab")
        page.locator("#login-button").press("Enter")
        time.sleep(3)
        print(f"Auth: {[(r['url'][:60], r['status']) for r in auth_reqs]}", flush=True)
    
    input("Enter to close...")
    browser.close()
