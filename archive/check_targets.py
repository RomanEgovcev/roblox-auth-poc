import os, time, subprocess, json, urllib.request

ext_path = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("[*] Chrome launched", flush=True)
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

    # Use CDP to create a target for the extension page
    import websocket
    ver = json.loads(urllib.request.urlopen("http://localhost:9222/json/version", timeout=5).read())
    browser_ws = ver['webSocketDebuggerUrl']
    cdp = websocket.create_connection(browser_ws, timeout=10)
    
    def cdp_send(method, params=None):
        global cdp_id
        cdp_id += 1
        msg = {"id": cdp_id, "method": method}
        if params: msg["params"] = params
        cdp.send(json.dumps(msg))
        return msg['id']
    cdp_id = 0
    
    def cdp_recv(timeout=5):
        cdp.settimeout(timeout)
        responses = []
        while True:
            try:
                msg = json.loads(cdp.recv())
                responses.append(msg)
                if 'id' in msg:
                    return responses
            except:
                break
        return responses
    
    # Open extension popup page via CDP
    print("[*] Opening extension popup via CDP...", flush=True)
    cdp_send("Target.createTarget", {
        "url": "chrome-extension://dknlfmjaanfblgfdfebhijalfmhmjjjo/assets/ip10n8.html"
    })
    time.sleep(1)
    responses = cdp_recv()
    for r in responses:
        print(f"  CDP: {str(r)[:200]}", flush=True)
    
    # Check targets again
    targets = json.loads(urllib.request.urlopen("http://localhost:9222/json", timeout=5).read())
    for t in targets:
        print(f"  target: type={t.get('type','?'):20s} url={t.get('url','?')[:150]}", flush=True)
    
    # Find the extension page and evaluate
    for t in targets:
        if 'chrome-extension' in t.get('url', ''):
            ext_page_ws = t.get('webSocketDebuggerUrl')
            print(f"\n[*] Found extension page: {ext_page_ws}", flush=True)
            
            ext_cdp = websocket.create_connection(ext_page_ws, timeout=10)
            ext_cdp.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
                "expression": """
                    (async () => {
                        try {
                            const data = await chrome.storage.local.get(null);
                            return JSON.stringify(data);
                        } catch(e) {
                            return 'error: ' + e.message;
                        }
                    })()
                """,
                "awaitPromise": True
            }}))
            result = json.loads(ext_cdp.recv())
            print(f"  Storage result: {str(result)[:500]}", flush=True)
            
            # Also get the extension key
            ext_cdp.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {
                "expression": """
                    (async () => {
                        try {
                            const config = await chrome.storage.local.get(['key', 'keys', 'config', 'settings']);
                            return JSON.stringify(config);
                        } catch(e) {
                            return 'error: ' + e.message;
                        }
                    })()
                """,
                "awaitPromise": True
            }}))
            result = json.loads(ext_cdp.recv())
            print(f"  Config result: {str(result)[:500]}", flush=True)
            
            ext_cdp.close()
            break
    
    cdp.close()

proc.kill()
