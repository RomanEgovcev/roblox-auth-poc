"""Debug current login page structure."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    # Full form analysis
    info = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        const form = document.querySelector('form');
        const allForms = document.querySelectorAll('form');
        return {
            button: {
                id: btn?.id,
                text: btn?.textContent,
                type: btn?.type,
                tag: btn?.tagName,
                class: btn?.className.substring(0, 200),
                'data-testid': btn?.getAttribute('data-testid'),
                rect: btn ? (() => {const r = btn.getBoundingClientRect(); return {x:r.x, y:r.y, w:r.width, h:r.height, visible: !!(r.width && r.height)}})() : null,
                listeners: btn?.getAttribute('__reactProps$') ? 'YES' : 'NO',
                disabled: btn?.disabled,
                ariaDisabled: btn?.getAttribute('aria-disabled'),
            },
            form: form ? {
                action: form.action,
                method: form.method,
                id: form.id,
                'data-testid': form.getAttribute('data-testid'),
            } : null,
            forms: Array.from(allForms).map(f => ({action: f.action, method: f.method, id: f.id})),
            // Check for React root
            reactRoot: !!document.getElementById('root') || !!document.getElementById('__next') || !!document.querySelector('[data-rr]'),
            // React version from __REACT_DEVTOOLS_GLOBAL_HOOK__
            reactVer: (() => {try {return window.__REACT_DEVTOOLS_GLOBAL_HOOK__?.renderers?.values()?.next()?.value?.version || 'unknown'} catch(e){return 'error'}})(),
        };
    }""")
    print(json.dumps(info, indent=2), flush=True)
    
    # Check all buttons
    buttons = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button')).map(b => ({
            id: b.id,
            text: b.textContent.substring(0, 50),
            type: b.type,
            class: b.className.substring(0, 100),
            visible: !!(b.getBoundingClientRect().width && b.getBoundingClientRect().height)
        }));
    }""")
    print(f"Buttons: {json.dumps(buttons, indent=2)}", flush=True)
    
    # Check page imports
    scripts = page.evaluate("""() => {
        return Array.from(document.scripts).map(s => ({
            src: s.src.substring(0, 150),
            id: s.id
        }));
    }""")
    print(f"Scripts: {json.dumps(scripts, indent=2)[:1000]}", flush=True)
    
    input("Check console...")
    browser.close()
