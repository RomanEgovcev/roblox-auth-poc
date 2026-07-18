"""Navigate to Arkose enforcement URL directly to see captcha."""
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
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    # Step 1: Get the challenge
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
        print(f"[-] No auth: {e}", flush=True)
    
    time.sleep(5)
    
    # Get Arkose URL from the iframe — try multiple times
    arkose_url = None
    for attempt in range(5):
        arkose_url = page.evaluate("""() => {
            // Search in all iframes including nested ones
            const allElements = document.querySelectorAll('*');
            const iframes = [];
            for (let el of allElements) {
                if (el.tagName === 'IFRAME') iframes.push(el);
            }
            const arkoseIframe = iframes.find(f => f.src && f.src.includes('arkoselabs'));
            return arkoseIframe ? arkoseIframe.src : null;
        }""")
        if arkose_url:
            print(f"[+] Arkose URL found on attempt {attempt+1}", flush=True)
            break
        time.sleep(1)
    
    if not arkose_url:
        # Also check the generic challenge container
        arkose_url = page.evaluate("""() => {
            const gc = document.getElementById('generic-challenge-container-proofofwork');
            if (gc) {
                const iframes = gc.querySelectorAll('iframe');
                if (iframes.length > 0) {
                    return Array.from(iframes).map(f => f.src).filter(Boolean);
                }
                // Check innerHTML for url
                return {innerHTML: gc.innerHTML.substring(0, 500)};
            }
            return {error: 'container not found'};
        }""")
        print(f"[-] Arkose URL not found. Container: {json.dumps(arkose_url)[:500]}", flush=True)
    
    if arkose_url:
        print(f"[+] Arkose URL: {arkose_url}", flush=True)
        
        # Navigate to the Arkose URL directly in a new tab
        page2 = browser.new_page()
        page2.goto(arkose_url, wait_until="domcontentloaded", timeout=30000)
        print(f"[*] Arkose page loaded: {page2.title()}, url: {page2.url[:150]}", flush=True)
        
        time.sleep(5)
        
        # Check for captcha elements
        arkose_content = page2.evaluate("""() => {
            return {
                title: document.title,
                body: document.body.innerHTML.substring(0, 1000),
                scripts: Array.from(document.scripts).map(s => s.src).filter(Boolean),
                iframes: Array.from(document.querySelectorAll('iframe')).map(f => f.src).filter(Boolean)
            };
        }""")
        print(f"[+] Arkose content: {json.dumps(arkose_content, indent=2)[:2000]}", flush=True)
        
        page2.screenshot(path="arkose_direct.png")
        time.sleep(5)
        
        # Also try to listen for captcha events
        page2.evaluate("""() => {
            window.addEventListener('message', function(e) {
                console.log('[CAPTCHA_MSG]', e.data);
            });
        }""")
        
        time.sleep(5)
        page2.screenshot(path="arkose_direct2.png")
        browser.close()
    else:
        print("[-] No Arkose URL found", flush=True)
        page.screenshot(path="no_arkose.png")
        time.sleep(5)
        browser.close()
