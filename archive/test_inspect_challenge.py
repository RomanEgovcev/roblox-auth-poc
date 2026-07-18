"""Inspect the proofofwork challenge container."""
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
    
    responses = []
    page.on("response", lambda r: responses.append({"u": r.url, "s": r.status}))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    page.evaluate(f"""() => {{
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        const u = document.getElementById('login-username');
        const p = document.getElementById('login-password');
        if (u) {{ setter.call(u, '{USER}'); u.dispatchEvent(new Event('input', {{bubbles: true}})); }}
        if (p) {{ setter.call(p, '{PASS}'); p.dispatchEvent(new Event('input', {{bubbles: true}})); }}
    }}""")
    time.sleep(1)
    
    page.click('.login-button', timeout=5000)
    time.sleep(5)
    
    # Inspect the challenge container
    chall_container = page.evaluate("""() => {
        const container = document.querySelector('[class*="generic-challenge-container"]');
        if (!container) return {error: 'no container'};
        
        function getElementInfo(el, depth=0) {
            if (!el || depth > 3) return null;
            const info = {
                tag: el.tagName,
                className: el.className.substring(0, 100),
                id: el.id,
                text: (el.textContent || '').trim().substring(0, 200),
                visible: el.offsetParent !== null,
                display: window.getComputedStyle(el).display,
                children: [],
            };
            if (el.shadowRoot) {
                info.shadowRoot = true;
                info.shadowChildren = Array.from(el.shadowRoot.children).map(c => getElementInfo(c, depth + 1));
            }
            for (const child of el.children) {
                info.children.push(getElementInfo(child, depth + 1));
            }
            return info;
        }
        
        const parent = container.parentElement;
        return {
            container: getElementInfo(container),
            parent: parent ? getElementInfo(parent) : null,
            html: container.innerHTML.substring(0, 1000),
            allText: container.textContent.substring(0, 500),
            dataAttrs: Object.keys(container.dataset).map(k => `${k}=${container.dataset[k]}`),
        };
    }""")
    print(f"\nChallenge container:", flush=True)
    print(json.dumps(chall_container, indent=2, default=str)[:3000], flush=True)
    
    # Check the require/define system for Challenge module
    challenge_mod = page.evaluate("""() => {
        // Check Roblox require
        if (window.Roblox && window.Roblox.require) {
            try {
                const challenge = window.Roblox.require('Roblox.Challenge');
                return {found: true, keys: Object.keys(challenge), 
                    methods: Object.keys(challenge).filter(k => typeof challenge[k] === 'function')};
            } catch(e) {
                return {requireError: e.message.substring(0, 200)};
            }
        }
        return {noRequire: true};
    }""")
    print(f"\nChallenge module: {json.dumps(challenge_mod, indent=2)}", flush=True)
    
    # Check auth responses
    auth_resp = [r for r in responses if '/v2/login' in r['u'] or 'auth.roblox.com' in r['u']]
    print(f"\nAuth responses ({len(auth_resp)}):", flush=True)
    for r in auth_resp:
        print(f"  [{r['s']}] {r['u'][:120]}", flush=True)
    
    time.sleep(2)
    browser.close()
