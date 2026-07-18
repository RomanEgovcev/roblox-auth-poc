"""Let Roblox client handle login natively via form."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Monitor ALL requests
    requests_log = []
    page.on("response", lambda r: requests_log.append({"url": r.url[:150], "status": r.status, "type": r.request.resource_type}))
    page.on("request", lambda r: requests_log.append({"req_url": r.url[:150], "method": r.method}))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Check login form structure and find React internals
    form_info = page.evaluate("""() => {
        const form = document.querySelector('form');
        if (!form) return {error: 'no form'};
        const inputs = form.querySelectorAll('input');
        const buttons = form.querySelectorAll('button');
        return {
            formId: form.id,
            inputs: Array.from(inputs).map(i => ({id: i.id, name: i.name, type: i.type, className: i.className})),
            buttons: Array.from(buttons).map(b => ({id: b.id, name: b.name, text: b.textContent?.trim()?.substring(0,30), className: b.className})),
            formAction: form.action,
        };
    }""")
    print("Form info:", json.dumps(form_info, indent=2), flush=True)
    
    # Find React fiber/event handlers on login button
    button_info = page.evaluate("""() => {
        const btn = document.querySelector('button[type="submit"], form button:last-child');
        if (!btn) return {error: 'no button'};
        const keys = Object.keys(btn).filter(k => k.startsWith('__react'));
        let handlerInfo = {};
        // Check React event handlers
        const reactKey = keys.find(k => k.includes('EventHandlers') || k.includes('Props'));
        if (reactKey) {
            handlerInfo.reactKey = reactKey;
            try {
                const props = Object.keys(btn[reactKey]).filter(k => !k.startsWith('__'));
                handlerInfo.props = props;
            } catch(e) {}
        }
        return {keys, handlerInfo, outerHTML: btn.outerHTML.substring(0, 300)};
    }""")
    print("Button info:", json.dumps(button_info, indent=2), flush=True)
    
    # Fill form using React's synthetic events
    fill_result = page.evaluate(f"""() => {{
        const usernameInput = document.querySelector('input[name="username"], input[id*="user"], input[id*="User"]');
        const passwordInput = document.querySelector('input[type="password"]');
        if (!usernameInput || !passwordInput) return {{error: 'inputs not found'}};
        
        // Set native value
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeInputValueSetter.call(usernameInput, '{USER}');
        usernameInput.dispatchEvent(new Event('input', {{bubbles: true}}));
        usernameInput.dispatchEvent(new Event('change', {{bubbles: true}}));
        
        nativeInputValueSetter.call(passwordInput, '{PASS}');
        passwordInput.dispatchEvent(new Event('input', {{bubbles: true}}));
        passwordInput.dispatchEvent(new Event('change', {{bubbles: true}}));
        
        return {{username: usernameInput.value, password: passwordInput.value}};
    }}""")
    print(f"\nFill result: {fill_result}", flush=True)
    
    time.sleep(1)
    
    # Now click the login button using React's event system
    # First try the native click
    time.sleep(1)
    
    # Try clicking real button
    print("\nClicking login button...", flush=True)
    
    # Use Playwright's click
    try:
        page.click('button[type="submit"]', timeout=5000)
        print("  Clicked via Playwright!", flush=True)
    except Exception as e:
        print(f"  Playwright click failed: {e}", flush=True)
        # Fall back to dispatchEvent
        page.evaluate("""() => {
            const btn = document.querySelector('button[type="submit"]');
            if (btn) {
                btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
            }
        }""")
        print("  Dispatched click event!", flush=True)
    
    # Wait and monitor
    time.sleep(10)
    
    # Check what happened
    current_url = page.url
    print(f"\nCurrent URL: {current_url}", flush=True)
    
    # Look for challenge-related responses
    chall_responses = [r for r in requests_log if 'chall' in str(r).lower()]
    print(f"\nChallenge-related requests ({len(chall_responses)}):", flush=True)
    for r in chall_responses[-10:]:
        print(f"  {r}", flush=True)
    
    # Check for auth requests
    auth_responses = [r for r in requests_log if 'auth' in str(r).lower()]
    print(f"\nAuth-related requests ({len(auth_responses)}):", flush=True)
    for r in auth_responses[-5:]:
        print(f"  {r}", flush=True)
    
    time.sleep(2)
    browser.close()
