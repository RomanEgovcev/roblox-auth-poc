"""Inspect the actual React onClick handler code and find what triggers the login."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Get the actual React handler code
    info = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        const reactKey = Object.keys(btn).find(k => k.startsWith('__reactProps'));
        const props = btn[reactKey];
        
        const result = {
            hasOnClick: typeof props.onClick === 'function',
            onClickSrc: props.onClick ? props.onClick.toString().substring(0, 2000) : 'none',
            allPropKeys: Object.keys(props).join(', ').substring(0, 500),
        };
        
        // Also check for __reactFiber to find the component tree
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        if (fiberKey) {
            const fiber = btn[fiberKey];
            const queue = fiber?.memoizedState?.queue;
            result.hasUpdateQueue = !!queue;
            
            // Walk up to find the component with state/handlers
            let node = fiber;
            let depth = 0;
            const handlers = {};
            while (node && depth < 30) {
                if (node.memoizedProps) {
                    const mps = node.memoizedProps;
                    if (mps.onClick) { handlers['onClick_depth_'+depth] = mps.onClick.toString().substring(0, 150); }
                    if (mps.onSubmit) { handlers['onSubmit_depth_'+depth] = mps.onSubmit.toString().substring(0, 150); }
                }
                if (node.stateNode && node.stateNode.__proto__ && node.stateNode.__proto__.constructor) {
                    const name = node.stateNode.__proto__.constructor.name;
                    if (name !== 'HTMLButtonElement' && name !== 'Object') {
                        handlers['component_depth_'+depth] = name;
                    }
                }
                node = node.return;
                depth++;
            }
            result.handlers = handlers;
        }
        
        return result;
    }""")
    print("=== React onClick Analysis ===", flush=True)
    print(json.dumps(info, indent=2)[:3000], flush=True)
    
    # Try to find the actual login call by looking at event listeners
    print("\n=== Event listener analysis ===", flush=True)
    # Chrome DevTools Protocol: getEventListeners
    # We can try findHandler via __reactEventHandlers
    event_info = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        
        // React internally stores events in root container
        const rootEl = document.getElementById('react-root') || document.getElementById('root') || document.querySelector('#__next') || document.body;
        
        const events = [];
        
        // Try finding React event system
        const rootFiberKey = Object.keys(rootEl).find(k => k.startsWith('__reactContainer'));
        if (rootFiberKey) {
            events.push('rootContainer found: ' + rootFiberKey);
        }
        
        // Check for React internal listener
        const listenerKey = Object.keys(btn).find(k => k.includes('listen'));
        if (listenerKey) events.push('listener key: ' + listenerKey);
        
        // Try to find React's internal event handling
        // In React 18, events are delegated to the root container
        const rootKeys = Object.keys(rootEl);
        events.push('root keys: ' + rootKeys.filter(k => k.startsWith('__react')).join(', '));
        
        return events;
    }""")
    print(json.dumps(event_info, indent=2), flush=True)
    
    # Let's try to dispatch a native click event more thoroughly
    print("\n=== Trying native click dispatch ===", flush=True)
    result = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        
        // Native click with all properties
        const event = new PointerEvent('click', {
            bubbles: true,
            cancelable: true,
            composed: true,
            pointerType: 'mouse',
            isPrimary: true,
            clientX: 500, clientY: 300,
            screenX: 500, screenY: 300,
        });
        const dispatched = btn.dispatchEvent(event);
        
        return {
            dispatched,
            defaultPrevented: event.defaultPrevented,
            composed: event.composed,
            isTrusted: event.isTrusted,
        };
    }""")
    print(f"  PointerEvent click: {result}", flush=True)
    
    # Try mousedown + mouseup + click sequence
    result = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        
        const types = ['mousedown', 'mouseup', 'click'];
        const results = types.map(type => {
            const e = new MouseEvent(type, {bubbles: true, cancelable: true, view: window});
            return {type, dispatched: btn.dispatchEvent(e)};
        });
        
        return results;
    }""")
    print(f"  MouseEvent sequence: {json.dumps(result)}", flush=True)
    
    input("Enter to close...")
    browser.close()
