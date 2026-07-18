import os, sys, time, subprocess, json, urllib.request
from playwright.sync_api import sync_playwright

ext_path = os.path.abspath(r'C:\Users\regov\Desktop\lua\chromium_automation')
profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')
username = sys.argv[1] if len(sys.argv) > 1 else "CheatingHitmanner"
password = sys.argv[2] if len(sys.argv) > 2 else ""

with sync_playwright() as p:
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    proc = subprocess.Popen(
        [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
         "--no-first-run", "--remote-debugging-port=9222",
         "--remote-allow-origins=*",
         "--disable-web-security",
         "--disable-quic",
         "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("[*] Chrome launched", flush=True)
    time.sleep(5)

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

    # Navigate to Roblox login
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    page.wait_for_selector("#login-username", timeout=30000)
    page.fill("#login-username", username)
    page.fill("#login-password", password)
    time.sleep(1)
    for sel in ["button[data-testid='login-button']", "#login-button"]:
        btn = page.query_selector(sel)
        if btn:
            btn.click(force=True)
            print(f"[*] Clicked {sel}", flush=True)
            break

    # Function to find extension SW
    def find_sw_target():
        targets = json.loads(urllib.request.urlopen("http://localhost:9222/json", timeout=5).read())
        for t in targets:
            if t.get('type') == 'service_worker' and t.get('url', '').startswith('chrome-extension://'):
                return t.get('webSocketDebuggerUrl')
        return None

    # Wait for SW to appear
    print("[*] Waiting for extension SW...", flush=True)
    sw_ws_url = None
    for _ in range(30):
        time.sleep(2)
        sw_ws_url = find_sw_target()
        if sw_ws_url:
            print(f"[+] Found SW: {sw_ws_url}", flush=True)
            break
        print("  waiting for SW...", flush=True)

    if not sw_ws_url:
        print("[-] SW not found", flush=True)
        proc.kill()
        exit(1)

    # Connect to SW via websocket
    import websocket
    ws = websocket.create_connection(sw_ws_url, timeout=10)
    ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
    ws.send(json.dumps({"id": 2, "method": "Network.enable"}))
    ws.send(json.dumps({"id": 3, "method": "Log.enable"}))
    ws.settimeout(0.3)
    try:
        while True: ws.recv()
    except: pass

    print("[*] Monitoring SW...", flush=True)

    # Monitor for requests
    captcha_body = None
    for _ in range(60):
        time.sleep(1)
        url = page.url
        info = f"  [{_+1}s] {url[:70]}"
        try:
            dom = page.evaluate("""() => {
                const captcha = document.querySelector('iframe[src*="arkoselabs"]');
                return captcha ? true : false;
            }""")
            if dom:
                info += " [CAPTCHA]"
        except:
            pass
        print(info, flush=True)
        if "home" in url:
            print("\n[+] LOGGED IN!", flush=True)
            for c in ctx.cookies():
                if c['name'] == '.ROBLOSECURITY':
                    print(f"[+] COOKIE: {c['value'][:50]}...")
            break

        # Poll SW messages
        while True:
            try:
                ws.settimeout(0.5)
                msg = json.loads(ws.recv())
                method = msg.get('method', '')
                params = msg.get('params', {})
                if method == 'Network.requestWillBeSent':
                    req = params.get('request', {})
                    url_req = req.get('url', '')
                    if 'nopecha' in url_req.lower() or 'api' in url_req.lower():
                        post_data = req.get('postData', '')
                        print(f"[SW-REQ] {req.get('method','')} {url_req[:150]}", flush=True)
                        if post_data:
                            print(f"  [SW-BODY] {post_data[:600]}", flush=True)
                            with open('last_sw_request.json', 'w') as f:
                                f.write(post_data)
                            captcha_body = post_data
                elif method == 'Network.responseReceived':
                    req = params.get('request', {})
                    resp = params.get('response', {})
                    url_req = req.get('url', '')
                    if 'nopecha' in url_req.lower() or 'api' in url_req.lower():
                        print(f"[SW-RES] {resp.get('status','')} {url_req[:150]}", flush=True)
                elif method == 'Network.loadingFailed':
                    url_req = params.get('request',{}).get('url','')
                    err = params.get('errorText','')
                    if 'nopecha' in url_req.lower() or 'api' in url_req.lower() or err:
                        print(f"[SW-FAIL] {url_req[:100]} -> {err}", flush=True)
                elif method == 'Runtime.consoleAPICalled':
                    for a in params.get('args', []):
                        print(f"[SW-CONSOLE] {a.get('value','')}", flush=True)
                elif method == 'Runtime.exceptionThrown':
                    print(f"[SW-EXC] {params.get('exceptionDetails',{}).get('text','')}", flush=True)
                elif method == 'Log.entryAdded':
                    txt = params.get('entry',{}).get('text','')
                    print(f"[SW-LOG] {txt[:200]}", flush=True)
            except websocket.WebSocketTimeoutException:
                break
            except Exception as e:
                print(f"[SW-POLL-ERR] {e}", flush=True)
                break

    proc.kill()
