"""Use route.fetch() to intercept /challenge/v1/continue and modify response."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    result = {"retried": False}
    
    def handle_continue(route, request):
        if "/challenge/v1/continue" not in request.url or request.method != "POST":
            route.continue_()
            return
        
        print(f"\n[INTERCEPT] /challenge/v1/continue", flush=True)
        
        try:
            # Fetch via browser's network (preserves PX headers)
            response = route.fetch()
            body = response.body()
            data = json.loads(body)
            print(f"  Original: {json.dumps(data)[:300]}", flush=True)
            
            if data.get("challengeType") == "captcha":
                data["challengeType"] = "proceed"
                data.pop("challengeMetadata", None)
                print(f"  Modified: {json.dumps(data)[:200]}", flush=True)
                
                hdrs = {}
                for k, v in response.headers.items():
                    lk = k.lower()
                    if lk not in ("transfer-encoding", "content-encoding", "content-security-policy", "content-length"):
                        hdrs[k] = v
                route.fulfill(status=response.status, headers=hdrs, body=json.dumps(data))
                return
            
            route.fulfill(response)
        except Exception as e:
            print(f"  Error: {e}", flush=True)
            try: route.continue_()
            except: pass
    
    page.route("**/apis.roblox.com/challenge/v1/continue**", handle_continue)
    
    def on_req(req):
        url = req.url
        if "/v2/login" in url and req.method == "POST":
            h = dict(req.headers)
            has_challenge = any("rblx-challenge" in k.lower() for k in h)
            if has_challenge:
                result["retried"] = True
                print(f"[LOGIN RETRY] Challenge headers present!", flush=True)
            print(f"[REQ] {req.method} {url[:80]} retry={has_challenge}", flush=True)
    
    def on_resp(resp):
        if "/v2/login" in resp.url:
            print(f"[RESP] {resp.status} {resp.url[:80]}", flush=True)
            try:
                b = resp.body()[:400]
                print(f"  Body: {b}", flush=True)
            except: pass
    
    page.on("request", on_req)
    page.on("response", on_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    # Mouse interaction
    page.evaluate("""() => {
        for (let i = 0; i < 20; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 100+i*30, clientY: 200+i*5, bubbles: true}));
        document.querySelector('input[name="username"]')?.focus();
        document.querySelector('input[name="username"]')?.dispatchEvent(new Event('focus', {bubbles: true}));
    }""")
    time.sleep(1)
    page.fill('input[name="username"]', 'testuser123')
    time.sleep(0.5)
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    page.evaluate("""() => {
        for (let i = 0; i < 10; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 500+i*20, clientY: 300+i*5, bubbles: true}));
    }""")
    time.sleep(0.5)
    
    t0 = time.time()
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
    print(f"Submitted, waiting...", flush=True)
    
    # Wait for flow with polling prints
    for i in range(30):
        time.sleep(1)
        if result["retried"]:
            print(f"[t={i+1}] LOGIN RETRY DETECTED!", flush=True)
            time.sleep(3)
            break
        if i % 5 == 4:
            print(f"[t={i+1}] still waiting...", flush=True)
    
    cookies = ctx.cookies()
    rs = [c for c in cookies if ".ROBLOSECURITY" in c["name"]]
    print(f"\nROBLOSECURITY: {len(rs)}", flush=True)
    if rs:
        print(f"Session: {rs[0]['value'][:60]}...", flush=True)
    
    print(f"Login retried: {result['retried']}", flush=True)
    browser.close()
