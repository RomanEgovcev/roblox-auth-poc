"""Try direct login POST with fetch to get challenge response."""
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
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[40:120]}" if any(x in r.url for x in ['auth', 'login', 'collector']) else "", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Get CSRF token and cookies
    page_info = page.evaluate("""() => {
        // Get XSRF token from meta tag
        const meta = document.querySelector('meta[name="csrf-token"]');
        const csrf = meta ? meta.getAttribute('content') : null;
        
        // Check for XSRF token in cookies
        const xsrfInput = document.querySelector('input[name="__RequestVerificationToken"]');
        const xsrf = xsrfInput ? xsrfInput.value : null;
        
        return {csrf, xsrf};
    }""")
    print(f"Tokens: {json.dumps(page_info)}", flush=True)
    
    # Try to submit login via fetch (as React would)
    print(f"\nTrying login POST...", flush=True)
    login_result = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST',
            credentials: 'include',
            headers: {{
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }},
            body: JSON.stringify({{
                ctype: 'Username',
                cvalue: '{USER}',
                password: '{PASS}',
            }}),
        }}).then(async r => {{
            const body = await r.text();
            const headers = {{}};
            r.headers.forEach((v, k) => {{ headers[k] = v; }});
            return {{
                status: r.status,
                headers: headers,
                body: body.substring(0, 500),
            }};
        }}).catch(e => ({{
            error: e.message,
        }}));
    }}""")
    print(f"Login response:", flush=True)
    print(json.dumps(login_result, indent=2)[:1000], flush=True)
    
    # Check for challenge tokens
    challenge = page.evaluate("""() => {
        // Check for any challenge-related cookies or DOM changes
        const chall = {};
        
        // Check _pxCaptcha cookie
        document.cookie.split(';').forEach(c => {
            const [k, v] = c.trim().split('=');
            if (k.includes('px') || k.includes('captcha') || k.includes('chall')) {
                chall[k] = v;
            }
        });
        
        return chall;
    }""")
    print(f"\nChallenge cookies: {json.dumps(challenge, indent=2)[:500]}", flush=True)
    
    time.sleep(5)
    browser.close()
