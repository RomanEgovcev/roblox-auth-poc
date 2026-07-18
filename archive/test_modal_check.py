"""Check login modal and requests after native click."""
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
    requests_out = []
    page.on("response", lambda r: responses.append({"url": r.url[50:200], "status": r.status, "type": r.request.resource_type}))
    page.on("request", lambda r: requests_out.append({"url": r.url[50:200], "method": r.method, "type": r.resource_type}))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    page.evaluate(f"""() => {{
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        const u = document.querySelector('input[name="username"]');
        const p = document.querySelector('input[type="password"]');
        if (u) {{ setter.call(u, '{USER}'); u.dispatchEvent(new Event('input', {{bubbles: true}})); }}
        if (p) {{ setter.call(p, '{PASS}'); p.dispatchEvent(new Event('input', {{bubbles: true}})); }}
    }}""")
    time.sleep(1)
    
    page.click('button[type="submit"]', timeout=5000)
    print("Clicked login!", flush=True)
    time.sleep(8)
    
    # Check modal content
    modal_info = page.evaluate("""() => {
        const modal = document.querySelector('.modal-dialog, [class*="modal"]');
        if (!modal) return {error: 'no modal'};
        return {
            html: modal.innerHTML.substring(0, 1000),
            text: modal.textContent.substring(0, 500),
            visible: modal.offsetParent !== null,
            display: window.getComputedStyle(modal).display,
        };
    }""")
    print(f"\nModal: {json.dumps(modal_info, indent=2)}", flush=True)
    
    # Check for challenge iframe
    iframes = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('iframe')).map(f => ({
            src: f.src.substring(0, 150),
            id: f.id,
            className: f.className.substring(0, 50),
            visible: f.offsetParent !== null,
        }));
    }""")
    print(f"\nIFrames: {json.dumps(iframes, indent=2)}", flush=True)
    
    # Check auth POSTs
    auth_posts = [r for r in responses if 'auth' in r.get('url', '').lower() and 'POST' in str(r)]
    print(f"\nAuth responses ({len(auth_posts)}):", flush=True)
    for r in auth_posts[:10]:
        print(f"  [{r['status']}] {r['url'][:80]}", flush=True)
    
    # Get challenge CSS/JS requests
    chall_assets = [r for r in responses if 'Challenge' in r.get('url', '')]
    print(f"\nChallenge assets ({len(chall_assets)}):", flush=True)
    for r in chall_assets:
        print(f"  [{r['status']}] {r['url'][:80]}", flush=True)
    
    # Check if there was a login POST
    login_posts = [r for r in responses if '/v2/login' in r.get('url', '') or '/login' in r.get('url', '')]
    print(f"\nLogin responses ({len(login_posts)}):", flush=True)
    for r in login_posts:
        print(f"  [{r['status']}] {r['url'][:80]}", flush=True)
    
    time.sleep(2)
    browser.close()
