"""Set values via evaluate (no blur) and check challenge container."""
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
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Set values via evaluate (no blur, proper React event)
    page.evaluate(f"""() => {{
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        const u = document.getElementById('login-username');
        const p = document.getElementById('login-password');
        if (u) {{ setter.call(u, '{USER}'); u.dispatchEvent(new Event('input', {{bubbles: true}})); u.dispatchEvent(new Event('change', {{bubbles: true}})); }}
        if (p) {{ setter.call(p, '{PASS}'); p.dispatchEvent(new Event('input', {{bubbles: true}})); p.dispatchEvent(new Event('change', {{bubbles: true}})); }}
    }}""")
    time.sleep(1)
    
    # Click
    page.click('.login-button', timeout=5000)
    print("Clicked!", flush=True)
    
    # Watch for challenge container
    for i in range(15):
        time.sleep(1)
        state = page.evaluate(f"""() => {{
            const chall = document.querySelector('[class*="generic-challenge"]');
            return {{
                hasChallenge: chall !== null,
                challHTML: chall ? chall.innerHTML.substring(0, 200) : '',
                challVisible: chall ? chall.offsetParent !== null : false,
                challClass: chall ? chall.className : '',
            }};
        }}""")
        if state['hasChallenge']:
            print(f"  [{i+1}s] Challenge found!", flush=True)
            print(f"    class: {state['challClass']}", flush=True)
            print(f"    html: {state['challHTML']}", flush=True)
            print(f"    visible: {state['challVisible']}", flush=True)
            break
        if i >= 4 and i % 5 == 0:
            print(f"  [{i+1}s] No challenge yet...", flush=True)
    
    print(f"\nFinal URL: {page.url}", flush=True)
    
    time.sleep(2)
    browser.close()
