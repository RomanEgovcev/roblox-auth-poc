"""Trace auth request - find what actually sends it."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")
patched = patched.replace("new EvalError", "new Error")

FETCH_OVERRIDE = """
const originalFetch = window.fetch;
window.fetch = function(...args) {
    console.log('[FETCH] Called:', args[0] instanceof Request ? args[0].url.substring(0,80) : String(args[0]).substring(0,80));
    return originalFetch.apply(this, arguments).then(async response => {
        console.log('[FETCH] Response:', response.url.substring(0,80), response.status);
        if (response.url.includes('auth.roblox.com') && response.url.includes('/v2/login')) {
            console.log('[FETCH] INTERCEPTING AUTH!');
            const clone = response.clone();
            const chalMeta = clone.headers.get('rblx-challenge-metadata');
            console.log('[FETCH] Challenge header present:', !!chalMeta);
            if (chalMeta && response.status === 403) {
                try {
                    let meta = JSON.parse(atob(chalMeta));
                    if (meta.sharedParameters) {
                        meta.sharedParameters.eligibleMethods = ['captcha', 'proofofwork'];
                        meta.sharedParameters.renderNativeChallenge = true;
                    }
                    const newMeta = btoa(JSON.stringify(meta));
                    const modHeaders = new Headers(clone.headers);
                    modHeaders.set('rblx-challenge-metadata', newMeta);
                    const body = await clone.text();
                    console.log('[FETCH] AUTH MODIFIED');
                    return new Response(body, {status: response.status, statusText: response.statusText, headers: modHeaders});
                } catch(e) { console.log('[FETCH] Error:', e); }
            }
        }
        return response;
    });
};
console.log('[FETCH] Override installed, original fetch captured');
"""

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.add_init_script(FETCH_OVERRIDE)
    
    logs = []
    page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text[:200]}"))
    
    # Track ALL auth requests via Playwright
    auth_requests = []
    
    def track_req(request):
        if 'auth.roblox.com' in request.url and '/v2/login' in request.url:
            auth_requests.append({
                'url': request.url[:150],
                'method': request.method,
                'headers': dict(request.headers),
                'post_data': request.post_data
            })
    
    page.on("request", track_req)
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        resp = response_info.value
        print(f"[+] Auth: {resp.status}", flush=True)
        
        # Check if our fetch override intercepted it
        has_fetch_intercept = any('[FETCH] INTERCEPTING AUTH' in log for log in logs)
        print(f"[+] Fetch override intercepted auth: {has_fetch_intercept}", flush=True)
        
        # Check auth request details
        for i, req in enumerate(auth_requests):
            print(f"\n[Auth Request {i}]:", flush=True)
            print(f"  URL: {req['url']}", flush=True)
            print(f"  Method: {req['method']}", flush=True)
            print(f"  Content-Type: {req['headers'].get('content-type', 'N/A')}", flush=True)
            print(f"  X-Requested-With: {req['headers'].get('x-requested-with', 'N/A')}", flush=True)
        
    except Exception as e:
        print(f"[-] Auth: {e}", flush=True)
    
    time.sleep(3)
    
    # Print relevant console logs
    print(f"\n=== Console logs (last 20) ===", flush=True)
    for log in logs[-20:]:
        print(f"  {log}", flush=True)
    
    page.screenshot(path="auth_request.png")
    
    time.sleep(5)
    browser.close()
