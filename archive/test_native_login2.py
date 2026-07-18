"""Proper native login through Roblox client."""
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
    
    responses = []
    page.on("response", lambda r: responses.append({"u": r.url[50:200], "s": r.status, "t": r.request.resource_type}))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Fill form using React-compatible method
    page.evaluate(f"""() => {{
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        const u = document.getElementById('login-username');
        const p = document.getElementById('login-password');
        if (u) {{ setter.call(u, '{USER}'); u.dispatchEvent(new Event('input', {{bubbles: true}})); u.dispatchEvent(new Event('change', {{bubbles: true}})); }}
        if (p) {{ setter.call(p, '{PASS}'); p.dispatchEvent(new Event('input', {{bubbles: true}})); p.dispatchEvent(new Event('change', {{bubbles: true}})); }}
    }}""")
    time.sleep(1)
    
    # Click the actual "Log In" button
    page.click('.login-button', timeout=5000)
    
    # Wait and monitor
    time.sleep(10)
    
    # Check all login/auth POSTs
    login_responses = [r for r in responses if '/v2/login' in r['u'] or '/login' in r['u']]
    print(f"\nLogin responses ({len(login_responses)}):", flush=True)
    for r in login_responses:
        print(f"  [{r['s']}] {r['u'][:100]} ({r['t']})", flush=True)
    
    # Check challenge responses
    chall_responses = [r for r in responses if 'chall' in r['u'].lower() or 'Challenge' in r['u']]
    print(f"\nChallenge responses ({len(chall_responses)}):", flush=True)
    for r in chall_responses:
        print(f"  [{r['s']}] {r['u'][:100]} ({r['t']})", flush=True)
    
    # Check current URL
    print(f"\nCurrent URL: {page.url}", flush=True)
    
    # Check if logged in or still on login page
    page_state = page.evaluate("""() => {
        const result = {};
        result.url = window.location.href;
        result.loginForm = document.getElementById('login-username') !== null;
        // Check for challenge-related DOM elements
        result.challElements = [];
        document.querySelectorAll('[class*="challenge" i], [id*="challenge" i]').forEach(el => {
            if (el.offsetParent !== null) result.challElements.push(el.className.substring(0, 80) || el.id.substring(0, 80));
        });
        // Check for game-core iframes (Arkose)
        result.iframes = Array.from(document.querySelectorAll('iframe')).filter(f => f.src).map(f => f.src.substring(0, 150));
        return result;
    }""")
    print(f"\nPage state: {json.dumps(page_state, indent=2)}", flush=True)
    
    time.sleep(2)
    browser.close()
