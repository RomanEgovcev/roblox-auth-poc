"""Debug all responses to find login POST."""
import os, time

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    all_responses = []
    page.on("response", lambda r: all_responses.append({"url": r.url[:200], "status": r.status}))
    
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
    
    # Check that button exists and is enabled
    btn_info = page.evaluate("""() => {
        const btn = document.querySelector('.login-button');
        if (!btn) return {error: 'no button'};
        return {
            disabled: btn.disabled,
            className: btn.className,
            text: btn.textContent.trim(),
            visible: btn.offsetParent !== null,
            rect: btn.getBoundingClientRect(),
        };
    }""")
    print(f"Login button: {btn_info}", flush=True)
    
    if btn_info.get('disabled'):
        print("Button is DISABLED - form validation failed!", flush=True)
    
    page.click('.login-button', timeout=5000)
    print("Clicked!", flush=True)
    
    time.sleep(10)
    
    # Find login-related responses
    login_urls = [r for r in all_responses if 'auth' in r['url'].lower() and 'login' in r['url'].lower()]
    print(f"\nAuth/login responses ({len(login_urls)}):", flush=True)
    for r in login_urls:
        print(f"  [{r['status']}] {r['url'][:120]}", flush=True)
    
    # Find POST requests
    post_urls = []
    page.on("request", lambda r: post_urls.append({"url": r.url[:200], "method": r.method}) if r.method == 'POST' else None)
    # Re-check with request hook
    for r in all_responses[:50]:
        if 'auth' in r['url'].lower():
            print(f"  ALL auth: [{r['status']}] {r['url'][:120]}", flush=True)
    
    time.sleep(2)
    browser.close()
