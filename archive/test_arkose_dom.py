"""Check created Arkose elements and challenge DOM in detail."""
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
    
    # Detailed DOM analysis
    dom_info = page.evaluate("""() => {
        const result = {};
        
        // Arkose elements
        const arkoseDiv = document.getElementById('arkose-0');
        result.arkoseDiv = arkoseDiv ? {
            innerHTML: arkoseDiv.innerHTML.substring(0, 500),
            childCount: arkoseDiv.children.length,
            tag: arkoseDiv.tagName,
            style: arkoseDiv.getAttribute('style') || ''
        } : null;
        
        // Challenge container
        const proofContainer = document.getElementById('generic-challenge-container-proofofwork');
        result.proofContainer = proofContainer ? {
            innerHTML: proofContainer.innerHTML.substring(0, 500),
            childCount: proofContainer.children.length,
            style: proofContainer.getAttribute('style') || ''
        } : null;
        
        // Check for iframes in the entire document
        const iframes = document.querySelectorAll('iframe');
        result.iframes = Array.from(iframes).map(f => ({
            src: f.src.substring(0, 200),
            id: f.id,
            style: f.getAttribute('style') || ''
        }));
        
        // Find all script tags with arkose in id
        const arkoseScripts = document.querySelectorAll('script[id*=\"arkose\"]');
        result.arkoseScripts = Array.from(arkoseScripts).map(s => ({
            id: s.id,
            src: s.src.substring(0, 200),
        }));
        
        return result;
    }""")
    
    print(f"\n=== DOM Analysis ===", flush=True)
    print(json.dumps(dom_info, indent=2)[:2000], flush=True)
    
    page.screenshot(path="arkose_dom.png")
    time.sleep(10)
    browser.close()
