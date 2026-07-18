"""Debug: track ALL Arkose responses."""
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
    return originalFetch.apply(this, arguments).then(async response => {
        const url = response.url;
        if (url.includes('auth.roblox.com') && url.includes('/v2/login') && response.status === 403) {
            const clone = response.clone();
            const chalMeta = clone.headers.get('rblx-challenge-metadata');
            if (chalMeta) {
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
                    return new Response(body, {status: response.status, statusText: response.statusText, headers: modHeaders});
                } catch(e) { console.log('[FETCH] Error:', e); }
            }
        }
        return response;
    });
};
"""

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.add_init_script(FETCH_OVERRIDE)
    
    arkose_requests = []
    arkose_responses = []
    
    def track_req(request):
        url = request.url
        if 'arkoselabs.roblox.com' in url or 'ecsv2.roblox.com' in url:
            arkose_requests.append({'url': url[:200], 'method': request.method, 'rtype': request.resource_type})
            print(f"[REQ] {request.resource_type:12s} {url[:150]}", flush=True)
    
    def track_resp(response):
        url = response.url
        if 'arkoselabs.roblox.com' in url or 'ecsv2.roblox.com' in url:
            arkose_responses.append({'url': url[:200], 'status': response.status, 'rtype': response.request.resource_type})
            print(f"[RES] {response.status:3d} {response.request.resource_type:12s} {url[:150]}", flush=True)
    
    page.on("request", track_req)
    page.on("response", track_resp)
    
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
    except Exception as e:
        print(f"[-] Auth: {e}", flush=True)
    
    # Wait 25 seconds and log all new Arkose requests/responses
    for i in range(25):
        time.sleep(1)
        count = len(arkose_responses)
        if i > 0 and i % 5 == 0:
            print(f"[*] {i+1}s: {count} Arkose responses so far", flush=True)
    
    print(f"\n[SUMMARY] Total Arkose requests: {len(arkose_requests)}", flush=True)
    print(f"[SUMMARY] Total Arkose responses: {len(arkose_responses)}", flush=True)
    print(f"\n--- All Arkose Requests ---", flush=True)
    for r in arkose_requests:
        print(f"  {r['method']:4s} {r['rtype']:12s} {r['url']}", flush=True)
    print(f"\n--- All Arkose Responses ---", flush=True)
    for r in arkose_responses:
        print(f"  {r['status']:3d} {r['rtype']:12s} {r['url']}", flush=True)
    
    page.screenshot(path="debug_full.png")
    
    time.sleep(5)
    browser.close()
