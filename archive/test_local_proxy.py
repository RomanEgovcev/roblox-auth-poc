import os, time, subprocess, json, urllib.request, socket, threading

# Start local proxy in a thread
import local_proxy
proxy_thread = threading.Thread(target=local_proxy.main, daemon=True)
proxy_thread.start()
time.sleep(1)
print("[*] Local proxy started", flush=True)

# Launch Chrome with local proxy
chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext_path = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--proxy-server=http://127.0.0.1:8888",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("[*] Chrome launched (local proxy :8888)", flush=True)
time.sleep(5)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = None
    for attempt in range(10):
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            print("[+] CDP connected", flush=True)
            break
        except:
            time.sleep(2)
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(15000)

    # Test cross-origin fetch
    print("[*] Testing cross-origin fetch via local proxy...", flush=True)
    page.goto("https://www.roblox.com", wait_until="domcontentloaded", timeout=15000)
    
    result = page.evaluate("""async () => {
        const results = {};
        for (const url of ['https://api.nopecha.com/v1/status', 'https://www.google.com']) {
            try {
                const resp = await fetch(url);
                const txt = await resp.text();
                results[url] = 'ok: ' + txt.slice(0, 100);
            } catch(e) {
                results[url] = 'error: ' + e.message;
            }
        }
        return JSON.stringify(results, null, 2);
    }""")
    print(f"  Results: {result}", flush=True)
    
    # Also test with no-cors
    result = page.evaluate("""async () => {
        try {
            const resp = await fetch('https://api.nopecha.com/v1/status', { mode: 'no-cors' });
            return 'ok: status=' + resp.status + ' type=' + resp.type;
        } catch(e) {
            return 'error: ' + e.message;
        }
    }""")
    print(f"  no-cors: {result}", flush=True)

    # Now test the actual login flow
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    page.wait_for_selector("#login-username", timeout=30000)
    page.fill("#login-username", "CheatingHitmanner")
    page.fill("#login-password", "TestAccountOpenCode123")
    time.sleep(1)
    for sel in ["button[data-testid='login-button']", "#login-button"]:
        btn = page.query_selector(sel)
        if btn:
            btn.click(force=True)
            print(f"[*] Clicked {sel}", flush=True)
            break
    
    # Poll for SW + captcha + auto-solve
    print("[*] Monitoring for captcha + SW...", flush=True)
    sw_found = None
    solved = False
    for i in range(120):
        time.sleep(1)
        
        # Check SW
        if not sw_found:
            try:
                targets = json.loads(urllib.request.urlopen("http://localhost:9222/json", timeout=2).read())
                for t in targets:
                    if t.get('type') == 'service_worker' and 'chrome-extension' in t.get('url', ''):
                        sw_found = t
                        print(f"\n[SW!] {t.get('url','')[:120]}", flush=True)
            except:
                pass
        
        url = page.url
        info = f"  [{i+1}s] {url[:70]}"
        try:
            dom = page.evaluate("() => !!document.querySelector('iframe[src*=\"arkoselabs\"]')")
            if dom:
                info += " [CAPTCHA]"
        except:
            pass
        if "home" in url:
            info += " [LOGGED IN!]"
            solved = True
        if sw_found:
            info += " [SW]"
        print(info, flush=True)
        if solved:
            print("\n[+] LOGGED IN!", flush=True)
            for c in ctx.cookies():
                if c['name'] == '.ROBLOSECURITY':
                    print(f"[+] COOKIE: {c['value'][:50]}...")
                    print(f"[+] FULL: {c['value']}")
            break

    # Check captured requests
    print("\n=== Captured API requests ===", flush=True)
    for r in local_proxy.captured_requests:
        print(f"  {r['method']} {r['url'][:100]} -> {r['status']}", flush=True)

proc.kill()
