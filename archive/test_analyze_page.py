"""Deep analysis of current login page event handling."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)  # extra wait
    
    # Check event listeners via injected function
    listeners = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        if (!btn) return {error: 'no button'};
        
        // Check for various event attachment patterns
        const result = {
            id: btn.id,
            outerHTML: btn.outerHTML.substring(0, 300),
            // Check React FIBER
            __reactFiber: btn._reactRootContainer ? 'yes' : 'no',
            __reactProps: btn.__reactProps ? 'yes' : 'no',
            // Check React internals
            reactInternal: Object.keys(btn).filter(k => k.startsWith('__react')).join(', '),
            // Check for jQuery
            jQuery: (() => { try { return typeof $ !== 'undefined' } catch(e) { return false } })(),
            // Check parent for delegation
            parentTag: btn.parentElement?.tagName,
            parentId: btn.parentElement?.id,
            grandparentTag: btn.parentElement?.parentElement?.tagName,
            grandparentId: btn.parentElement?.parentElement?.id,
        };
        
        // Check all ancestors for onclick or event attributes
        let el = btn;
        let level = 0;
        while (el && level < 5) {
            const attrs = {};
            for (const a of el.attributes || []) attrs[a.name] = a.value.substring(0, 100);
            if (el.onclick) attrs['**onclick**'] = el.onclick.toString().substring(0, 200);
            if (Object.keys(attrs).length > 0) result['level_' + level] = attrs;
            el = el.parentElement;
            level++;
        }
        
        return result;
    }""")
    print("=== Button analysis ===", flush=True)
    print(json.dumps(listeners, indent=2), flush=True)
    
    # Check what scripts are actually executing
    print("\n=== Console errors/warnings ===", flush=True)
    page.on("console", lambda msg: print(f"  [{msg.type}] {msg.text[:200]}", flush=True))
    
    # Try the SECOND form (login form)
    print("\n=== Login form analysis ===", flush=True)
    form_info = page.evaluate("""() => {
        const forms = document.querySelectorAll('form');
        return Array.from(forms).map((f, i) => ({
            idx: i,
            action: f.action,
            method: f.method,
            id: f.id,
            inputs: Array.from(f.querySelectorAll('input')).map(inp => ({
                name: inp.name,
                type: inp.type,
                id: inp.id,
                value: inp.value.substring(0, 50)
            })),
            buttons: Array.from(f.querySelectorAll('button')).map(b => ({
                id: b.id,
                type: b.type,
                text: b.textContent.substring(0, 50)
            }))
        }));
    }""")
    print(json.dumps(form_info, indent=2), flush=True)
    
    # Check what the login-button actually contains
    print("\n=== Button DOM detail ===", flush=True)
    btn_html = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        return {
            html: btn.innerHTML.substring(0, 500),
            classes: btn.className,
            dataAttrs: Object.keys(btn.dataset),
            childCount: btn.children.length,
            childHTML: Array.from(btn.children).map(c => c.outerHTML.substring(0, 100))
        };
    }""")
    print(json.dumps(btn_html, indent=2), flush=True)
    
    input("Press Enter to close...")
    browser.close()
