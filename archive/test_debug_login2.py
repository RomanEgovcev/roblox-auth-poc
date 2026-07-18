"""Debug login POST - fix hook timing."""
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
    
    responses = []
    requests = []
    page.on("response", lambda r: responses.append({"url": r.url[:200], "status": r.status}))
    page.on("request", lambda r: requests.append({"url": r.url[:200], "method": r.method}))
    
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
    
    btn_info = page.evaluate("""() => {
        const btn = document.querySelector('.login-button');
        if (!btn) return {error: 'no button'};
        return {disabled: btn.disabled, className: btn.className, text: btn.textContent.trim()};
    }""")
    print(f"Button: {btn_info}", flush=True)
    
    page.click('.login-button', timeout=5000)
    print("Clicked!", flush=True)
    
    time.sleep(10)
    
    # Find login POSTs
    auth_posts = [r for r in requests if 'auth' in r['url'].lower() and r['method'] == 'POST']
    print(f"\nAuth POST requests ({len(auth_posts)}):", flush=True)
    for r in auth_posts:
        print(f"  {r['url'][:120]}", flush=True)
    
    auth_responses = [r for r in responses if 'auth' in r['url'].lower() and 'login' in r['url'].lower()]
    print(f"\nAuth login responses ({len(auth_responses)}):", flush=True)
    for r in auth_responses:
        print(f"  [{r['status']}] {r['url'][:120]}", flush=True)
    
    # If no auth posts, check what requests went through
    if not auth_posts:
        all_posts = [r for r in requests if r['method'] == 'POST']
        print(f"\nALL POST requests ({len(all_posts)}):", flush=True)
        for r in all_posts[:20]:
            print(f"  {r['url'][:120]}", flush=True)
    
    time.sleep(2)
    browser.close()
