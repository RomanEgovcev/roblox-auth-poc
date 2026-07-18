"""Full monitoring - requests, responses, DOM mutations."""
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
    
    log = []
    page.on("request", lambda r: log.append({"t": time.time(), "type": "REQ", "url": r.url[:150], "m": r.method}))
    page.on("response", lambda r: log.append({"t": time.time(), "type": "RES", "url": r.url[:150], "s": r.status}))
    
    # DOM mutation observer
    page.evaluate("""() => {
        window.__challengeLog = [];
        const obs = new MutationObserver((mutations) => {
            for (const m of mutations) {
                for (const node of m.addedNodes) {
                    if (node.nodeType === 1 && node.className && node.className.includes('challenge')) {
                        window.__challengeLog.push({time: Date.now(), class: node.className, html: node.innerHTML.substring(0, 200)});
                    }
                }
            }
        });
        obs.observe(document.body, {childList: true, subtree: true});
    }""")
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    page.evaluate(f"""() => {{
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        const u = document.getElementById('login-username');
        const p = document.getElementById('login-password');
        if (u) {{ setter.call(u, '{USER}'); u.dispatchEvent(new Event('input', {{bubbles: true}})); u.dispatchEvent(new Event('change', {{bubbles: true}})); }}
        if (p) {{ setter.call(p, '{PASS}'); p.dispatchEvent(new Event('input', {{bubbles: true}})); p.dispatchEvent(new Event('change', {{bubbles: true}})); }}
    }}""")
    time.sleep(1)
    
    click_time = time.time()
    page.click('.login-button', timeout=5000)
    print("Clicked!", flush=True)
    
    time.sleep(10)
    
    # Show auth-related events after click
    auth_events = [e for e in log if 'auth.roblox' in e['url'] and e['t'] >= click_time]
    print(f"\nAuth events after click ({len(auth_events)}):", flush=True)
    for e in auth_events:
        dt = round(e['t'] - click_time, 2)
        if e['type'] == 'REQ':
            print(f"  [{dt:+.2f}s] REQ  {e['m']} {e['url'][:100]}", flush=True)
        else:
            print(f"  [{dt:+.2f}s] RES  {e['s']} {e['url'][:100]}", flush=True)
    
    # All POSTs after click
    posts_after = [e for e in log if e['type'] == 'REQ' and e['m'] == 'POST' and e['t'] >= click_time]
    print(f"\nAll POSTs after click ({len(posts_after)}):", flush=True)
    for e in posts_after[:15]:
        dt = round(e['t'] - click_time, 2)
        print(f"  [{dt:+.2f}s] {e['url'][:100]}", flush=True)
    
    # Check DOM mutation log
    dom_log = page.evaluate("() => window.__challengeLog || []")
    if dom_log:
        print(f"\nDOM mutations with 'challenge':", flush=True)
        for entry in dom_log:
            print(f"  {json.dumps(entry)[:200]}", flush=True)
    else:
        print("\nNo challenge DOM mutations detected.", flush=True)
    
    time.sleep(2)
    browser.close()
