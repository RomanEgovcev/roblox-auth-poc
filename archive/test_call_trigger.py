"""Call triggerCaptcha directly and trace the form submit handler."""
import os, time, json, sys

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
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    enf_frames = []
    page.on("frameattached", lambda f: enf_frames.append(f) 
             if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url else None)
    page.on("framenavigated", lambda f: enf_frames.append(f) 
             if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(8)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    
    # Find what 'S' is in triggerCaptcha
    print("=== Tracing triggerCaptcha ===", flush=True)
    s_info = page.evaluate("""() => {
        // triggerCaptcha is function P(){S.triggerCaptcha()}
        // Find S in enclosing scope
        // Try to get the function's closure
        const fn = triggerCaptcha;
        const fnStr = fn.toString();
        
        // Try to find S by searching scopes
        // S might be from React component
        const btn = document.getElementById('login-button');
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        let fiber = btn[fiberKey];
        let depth = 0;
        while (fiber && depth < 30) {
            const state = fiber.memoizedState;
            const props = fiber.memoizedProps;
            if (state && typeof state === 'object') {
                for (let k in state) {
                    if (state[k]?.triggerCaptcha) {
                        return {found: 'memoizedState.' + k, depth, stateKey: k};
                    }
                }
            }
            if (props?.onClick?.toString() === fnStr) {
                return {found: 'onClick', depth, props: Object.keys(props).slice(0, 10)};
            }
            fiber = fiber.return;
            depth++;
        }
        
        return {
            fnStr: fnStr.substring(0, 100),
            notFound: true,
        };
    }""")
    print(f"  {json.dumps(s_info)[:500]}", flush=True)
    
    # Call triggerCaptcha and wait for enforcement
    print("\n[2] Calling triggerCaptcha()...", flush=True)
    page.evaluate("triggerCaptcha()")
    
    print("  Waiting 10s for enforcement...", flush=True)
    time.sleep(10)
    
    print(f"  Enforcement frames: {len(enf_frames)}", flush=True)
    if enf_frames:
        print(f"  URL: {enf_frames[0].url[:250]}", flush=True)
    
    # Try the React onClick handler directly (find f)
    print("\n[3] Finding f() in onClick handler...", flush=True)
    f_info = page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        const props = Object.values(btn).find(v => v?.onClick);
        if (!props) return 'no props';
        
        const handler = props.onClick; // function(e){return f()}
        
        // The handler calls f() - let's find f
        // We can try evaluating f in the handler's scope
        // But f is likely a closure variable from the React component
        
        // Let's try to get f by reading the handler's source and looking at the scope chain
        // Since this is React, f is likely bound in the same component
        
        // Alternative approach: just call the handler directly
        // The form should submit
        return {
            handlerStr: handler.toString().substring(0, 100),
            // Try to get the form submit handler
            formOnSubmit: document.getElementById('login-form')?.onsubmit?.toString().substring(0, 200) || 'none',
        };
    }""")
    print(f"  {json.dumps(f_info)[:500]}", flush=True)
    
    # Try calling the React onClick directly
    print("\n[4] Calling React onClick directly...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        const props = Object.values(btn).find(v => v?.onClick);
        if (props?.onClick) {
            // Create a synthetic event
            const event = new MouseEvent('click', {bubbles: true, cancelable: true});
            Object.defineProperty(event, 'isTrusted', {value: true});
            props.onClick(event);
        }
    }""")
    
    print("  Waiting 15s for auth + game-core...", flush=True)
    time.sleep(15)
    
    print(f"\n  Enforcement frames: {len(enf_frames)}", flush=True)
    for e in enf_frames:
        print(f"    {e.url[:200]}", flush=True)
    
    print(f"  URL: {page.url[:200]}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    browser.close()
