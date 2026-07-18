"""Examine login button's React event handler."""
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
    
    # Deep inspect login button
    btn_info = page.evaluate("""() => {
        const btn = document.querySelector('.login-button');
        if (!btn) return {error: 'no button'};
        
        // Get React fiber
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        const propsKey = Object.keys(btn).find(k => k.startsWith('__reactProps'));
        
        const fiber = btn[fiberKey];
        const props = btn[propsKey];
        
        // Trace the fiber tree up to find the component with form submission
        let f = fiber;
        let components = [];
        let depth = 0;
        while (f && depth < 20) {
            const tag = f.tag;
            const type = f.type;
            let typeName = '';
            if (typeof type === 'function') typeName = type.name || type.toString().substring(0, 60);
            else if (typeof type === 'string') typeName = type;
            else typeName = String(type).substring(0, 60);
            
            components.push({
                tag: tag,
                type: type ? typeName : 'null',
                memoizedState: f.memoizedState ? 'present' : 'none',
                effectTag: f.effectTag,
            });
            f = f.return;
            depth++;
        }
        
        return {
            props: Object.keys(props || {}),
            onClickPresent: props && typeof props.onClick === 'function',
            onClickStr: props && props.onClick ? props.onClick.toString().substring(0, 500) : 'N/A',
            fiberTag: fiber ? fiber.tag : 'N/A',
            fiberType: fiber && fiber.type ? (typeof fiber.type === 'function' ? fiber.type.name : String(fiber.type).substring(0, 80)) : 'N/A',
            componentTree: components,
        };
    }""")
    
    print(f"Login button handler:", flush=True)
    print(json.dumps(btn_info, indent=2)[:2000], flush=True)
    
    # Also check the form parent
    form_info = page.evaluate("""() => {
        const btn = document.querySelector('.login-button');
        if (!btn) return {};
        const form = btn.closest('form');
        if (form) {
            return {
                formAction: form.action,
                formId: form.id,
                formClass: form.className,
                hasOnSubmit: Object.keys(form).some(k => k.includes('reactProps') && form[k] && form[k].onSubmit),
            };
        }
        // Find closest parent with role="form" or similar
        const parent = btn.parentElement;
        return {parentTag: parent ? parent.tagName : 'none', parentClass: parent ? parent.className : 'none'};
    }""")
    print(f"\nForm info: {json.dumps(form_info, indent=2)}", flush=True)
    
    time.sleep(2)
    browser.close()
