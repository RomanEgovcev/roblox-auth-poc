"""Patched PX + full network logging after login click."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")
patched = patched.replace("new EvalError", "new Error")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080},
    )
    page = context.new_page()
    
    STEALTH_JS = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """
    page.add_init_script(STEALTH_JS)
    
    all_requests = []
    
    def track_all(req):
        all_requests.append({
            'url': req.url[:120],
            'method': req.method,
            'time': time.time()
        })
    
    page.on("request", track_all)
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    # Clear requests before login click
    all_requests.clear()
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    
    auth_captured = [False]
    
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        resp = response_info.value
        print(f"[+] Auth response: {resp.status}", flush=True)
        auth_captured[0] = True
        
    except Exception as e:
        print(f"[-] No auth response: {e}", flush=True)
    
    # Wait for additional requests after auth response
    print("[*] Waiting 5s for post-auth requests...", flush=True)
    time.sleep(5)
    
    # Group and display requests
    auth_reqs = [r for r in all_requests if 'auth.roblox' in r['url']]
    px_reqs = [r for r in all_requests if '.px' in r['url'] or 'px-cdn' in r['url'] or 'px-cloud' in r['url']]
    arkose_reqs = [r for r in all_requests if 'arkose' in r['url'] or 'funcaptcha' in r['url'] or 'api.arkoselabs' in r['url']]
    challenge_reqs = [r for r in all_requests if 'challenge' in r['url'] or 'proof' in r['url']]
    
    print(f"\n=== Requests after click ===", flush=True)
    print(f"Auth: {len(auth_reqs)}", flush=True)
    for r in auth_reqs:
        print(f"  {r['method']} {r['url']}", flush=True)
    
    print(f"PX: {len(px_reqs)}", flush=True)
    for r in px_reqs:
        print(f"  {r['method']} {r['url']}", flush=True)
    
    print(f"Arkose: {len(arkose_reqs)}", flush=True)
    for r in arkose_reqs:
        print(f"  {r['method']} {r['url']}", flush=True)
    
    print(f"Challenge: {len(challenge_reqs)}", flush=True)
    
    # List ALL unique domains
    domains = set()
    for r in all_requests:
        from urllib.parse import urlparse
        try:
            domains.add(urlparse(r['url']).netloc)
        except:
            pass
    print(f"\nAll domains ({len(domains)}):", flush=True)
    for d in sorted(domains):
        print(f"  {d}", flush=True)
    
    print(f"\nTotal requests: {len(all_requests)}", flush=True)
    
    page.screenshot(path="network_log.png")
    time.sleep(10)
    browser.close()
