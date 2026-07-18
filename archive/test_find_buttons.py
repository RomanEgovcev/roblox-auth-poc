"""Find the actual login button and form."""
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
    
    # Find ALL buttons and their info
    all_buttons = page.evaluate("""() => {
        const buttons = document.querySelectorAll('button');
        return Array.from(buttons).map(b => ({
            text: b.textContent.trim().substring(0, 50),
            id: b.id,
            className: b.className.substring(0, 80),
            type: b.type,
            visible: b.offsetParent !== null,
            rect: (function() { const r = b.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; })(),
            reactHandlers: Object.keys(b).filter(k => k.startsWith('__reactProps')).map(k => {
                const props = b[k];
                if (!props || typeof props !== 'object') return null;
                return Object.keys(props).filter(p => p.startsWith('on')).join(',');
            }).filter(Boolean),
        }));
    }""")
    print(f"\nAll buttons ({len(all_buttons)}):", flush=True)
    for b in all_buttons:
        print(f"  text='{b['text']}' type={b['type']} visible={b['visible']} rect={b['rect']} handlers={b['reactHandlers']}", flush=True)
        print(f"    class={b['className']}", flush=True)
    
    # Find input fields
    all_inputs = page.evaluate("""() => {
        const inputs = document.querySelectorAll('input');
        return Array.from(inputs).map(i => ({
            id: i.id,
            name: i.name,
            type: i.type,
            placeholder: i.placeholder,
            className: i.className.substring(0, 60),
            visible: i.offsetParent !== null,
        }));
    }""")
    print(f"\nAll inputs ({len(all_inputs)}):", flush=True)
    for i in all_inputs:
        print(f"  id='{i['id']}' name='{i['name']}' type='{i['type']}' placeholder='{i['placeholder']}'", flush=True)
    
    time.sleep(2)
    browser.close()
