"""Intercept /challenge/v1/continue with longer wait."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

saw_continue = [False]

def handle_continue(route, request):
    if "/challenge/v1/continue" not in request.url or request.method != "POST":
        route.continue_()
        return
    
    saw_continue[0] = True
    print(f"\n=== INTERCEPTED /challenge/v1/continue ===", flush=True)
    
    try:
        # Fetch via browser's network (preserves PX headers)
        response = route.fetch()
        body = response.body()
        data = json.loads(body)
        print(f"Original response: {json.dumps(data)[:400]}", flush=True)
        
        if data.get("challengeType") == "captcha":
            # Change captcha to proceed
            data["challengeType"] = "proceed"
            data.pop("challengeMetadata", None)
            print(f"Modified: {json.dumps(data)[:200]}", flush=True)
            
            hdrs = {}
            for k, v in response.headers.items():
                lk = k.lower()
                if lk not in ("transfer-encoding", "content-encoding", "content-length"):
                    hdrs[k] = v
            route.fulfill(status=response.status, headers=hdrs, body=json.dumps(data))
            return
        
        route.fulfill(response)
    except Exception as e:
        print(f"route.fetch error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        try: route.continue_()
        except: pass

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    page.route("**/apis.roblox.com/challenge/v1/continue**", handle_continue)
    
    login_retried = [False]
    
    def on_req(req):
        url = req.url
        if "/v2/login" in url and req.method == "POST":
            h = dict(req.headers)
            has_headers = any("rblx-challenge" in k.lower() for k in h)
            if has_headers:
                login_retried[0] = True
                print(f"\n*** LOGIN RETRY WITH CHALLENGE HEADERS! ***", flush=True)
            else:
                print(f"[REQ] POST /v2/login first attempt", flush=True)
    
    def on_resp(resp):
        if "/v2/login" in resp.url:
            try:
                b = resp.body()[:300]
                print(f"[RESP] /v2/login {resp.status} body={b}", flush=True)
            except:
                print(f"[RESP] /v2/login {resp.status}", flush=True)
    
    page.on("request", on_req)
    page.on("response", on_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    # Mouse
    page.evaluate("""() => {
        for (let i = 0; i < 30; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 100+i*20, clientY: 200+i*5, bubbles: true}));
        document.querySelector('input[name="username"]')?.focus();
    }""")
    time.sleep(1)
    page.fill('input[name="username"]', 'testuser123')
    time.sleep(0.5)
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    page.evaluate("""() => {
        for (let i = 0; i < 15; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 500+i*20, clientY: 300+i*5, bubbles: true}));
    }""")
    time.sleep(0.5)
    
    page.evaluate("""() => {
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        function walk(f, d) {
            if (!f || d > 20) return null;
            if (f.memoizedProps && typeof f.memoizedProps.onFormSubmit === 'function') {
                f.memoizedProps.onFormSubmit();
                return 'ok';
            }
            return walk(f.child, d+1) || walk(f.sibling, d);
        }
        return walk(root[key], 0);
    }""")
    print(f"[t=0] Submitted", flush=True)
    
    for i in range(60):
        time.sleep(1)
        if saw_continue[0]:
            print(f"[t={i+1}] /challenge/v1/continue intercepted!", flush=True)
        if login_retried[0]:
            print(f"[t={i+1}] LOGIN RETRY DETECTED!", flush=True)
            time.sleep(2)
            break
        if i % 10 == 9:
            print(f"[t={i+1}] waiting... (continue={saw_continue[0]}, retry={login_retried[0]})", flush=True)
    
    print(f"\n=== RESULTS ===", flush=True)
    print(f"Continue intercepted: {saw_continue[0]}", flush=True)
    print(f"Login retried: {login_retried[0]}", flush=True)
    
    cookies = ctx.cookies()
    rs = [c for c in cookies if ".ROBLOSECURITY" in c["name"]]
    print(f"ROBLOSECURITY: {len(rs)}", flush=True)
    if rs:
        print(f"Session: {rs[0]['value'][:60]}...", flush=True)
    
    browser.close()
