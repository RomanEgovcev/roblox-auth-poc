"""Wait for FunCaptcha to render in the enforcement iframe."""
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
    
    arkose_responses = []
    
    def track_arkose(response):
        if 'arkoselabs.roblox.com' in response.url:
            arkose_responses.append({"url": response.url[:150], "status": response.status, "type": response.request.resource_type})
    
    page.on("response", track_arkose)
    
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
    
    time.sleep(3)
    
    # Make the arkose iframe visible
    page.evaluate("""() => {
        const gc = document.getElementById('generic-challenge-container-proofofwork');
        if (gc) gc.style.display = 'block';
        const ad = document.getElementById('arkose-0');
        if (ad) ad.style.display = 'block';
        const iframes = document.querySelectorAll('iframe');
        for (let f of iframes) {
            if (f.src.includes('arkoselabs')) {
                f.style.visibility = 'visible';
                f.style.opacity = '1';
            }
        }
    }""")
    
    # Wait for captcha to render
    print("[*] Waiting for captcha...", flush=True)
    for i in range(20):
        # Check the arkose page for captcha elements
        has_captcha = page.evaluate("""() => {
            const iframes = document.querySelectorAll('iframe');
            for (let f of iframes) {
                if (f.src.includes('arkoselabs')) {
                    try {
                        const doc = f.contentDocument || f.contentWindow.document;
                        if (doc) {
                            const app = doc.getElementById('app');
                            if (app && app.innerHTML.length > 50) {
                                return {rendered: true, html: app.innerHTML.substring(0, 200)};
                            }
                            return {rendered: false, htmlLen: app ? app.innerHTML.length : 0};
                        }
                    } catch(e) {
                        return {error: e.message};
                    }
                }
            }
            return {error: 'iframe not found'};
        }""")
        
        if has_captcha.get('rendered'):
            print(f"[+] Captcha rendered at {i}s!", flush=True)
            print(f"  HTML: {has_captcha.get('html','')}", flush=True)
            break
        
        time.sleep(1)
    else:
        print(f"[-] Captcha not rendered after 20s", flush=True)
        print(f"  Last state: {json.dumps(has_captcha)}", flush=True)
    
    # Print Arkose network requests
    print(f"\n=== Arkose network requests ({len(arkose_responses)}) ===", flush=True)
    for r in arkose_responses:
        print(f"  [{r['status']}] {r['type']} {r['url']}", flush=True)
    
    page.screenshot(path="captcha_check.png")
    time.sleep(10)
    browser.close()
