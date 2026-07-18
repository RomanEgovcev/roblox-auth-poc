"""Debug WebWorker and challenge flow - capture ALL errors and messages."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Capture everything
    all_requests = []
    def on_req(req):
        all_requests.append({"url": req.url, "method": req.method, "time": time.time()})
    def on_resp(resp):
        all_requests.append({"url": resp.url, "status": resp.status, "resp_time": time.time()})
        if "pow-puzzle" in resp.url or "worker" in resp.url.lower() or "/v2/login" in resp.url:
            print(f"[RESP {resp.status}] {resp.url}", flush=True)
    def on_req_fail(req):
        print(f"[FAILED] {req.method} {req.url}: {req.failure}", flush=True)
    def on_console(msg):
        text = msg.text
        if "error" in text.lower() or "uncaught" in text.lower() or "exception" in text.lower() or "fail" in text.lower():
            print(f"[CONSOLE_ERROR] {text[:300]}", flush=True)
        elif "worker" in text.lower() or "challenge" in text.lower() or "proof" in text.lower():
            print(f"[CONSOLE_CHALLENGE] {text[:300]}", flush=True)
    
    page.on("request", on_req)
    page.on("response", on_resp)
    page.on("requestfailed", on_req_fail)
    page.on("pageerror", lambda err: print(f"[PAGE_ERROR] {err}", flush=True))
    page.on("console", on_console)
    
    # Inject error interceptor BEFORE page loads
    page.add_init_script("""() => {
        window.addEventListener('error', function(e) {
            console.error('GLOBAL_ERROR:', e.message, e.filename, e.lineno);
        });
        window.addEventListener('unhandledrejection', function(e) {
            console.error('UNHANDLED_REJECTION:', e.reason);
        });
        // Monitor WebWorker creation
        const origWorker = window.Worker;
        window.Worker = function(url, opts) {
            console.log('WORKER_CREATED:', url);
            const w = new origWorker(url, opts);
            const origPost = w.postMessage;
            w.postMessage = function(msg) {
                console.log('WORKER_POSTMESSAGE:', JSON.stringify(msg).substring(0, 200));
                return origPost.call(this, msg);
            };
            w.addEventListener('message', function(e) {
                console.log('WORKER_MESSAGE:', JSON.stringify(e.data).substring(0, 200));
            });
            w.addEventListener('error', function(e) {
                console.error('WORKER_ERROR:', e.message);
            });
            return w;
        };
        window.Worker.prototype = origWorker.prototype;
    }""")
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    print("Page loaded", flush=True)
    
    # Fill credentials
    page.fill('input[name="username"]', "testuser123")
    page.fill('input[name="password"]', "TestPassword123!")
    time.sleep(1)
    
    # Trigger onFormSubmit
    page.evaluate("""() => {
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        if (!key) return;
        function walk(f, d) {
            if (!f || d > 20) return;
            if (f.memoizedProps && f.memoizedProps.onFormSubmit) {
                f.memoizedProps.onFormSubmit();
                return;
            }
            if (f.child) walk(f.child, d+1);
            if (f.sibling) walk(f.sibling, d);
        }
        walk(root[key], 0);
    }""")
    
    # Wait for activity
    time.sleep(30)
    
    print(f"\n=== ALL pow/worker requests ===", flush=True)
    for r in all_requests:
        if "pow" in r["url"] or "worker" in r["url"].lower():
            print(f"  {r}", flush=True)
    
    time.sleep(3)
    browser.close()
