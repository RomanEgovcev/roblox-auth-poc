"""Arkose iframe is loaded but hidden — check its content and try to show it."""
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
        args=['--disable-blink-features=AutomationControlled'],
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
    
    # Check ALL frames including about:blank
    print(f"\n=== ALL FRAMES ({len(page.frames)}) ===", flush=True)
    for i, f in enumerate(page.frames):
        print(f"  [{i}] url='{f.url[:150]}' name='{f.name}'", flush=True)
    
    # Make arkose visible
    show_result = page.evaluate("""() => {
        const results = {};
        
        // Find the arkose iframe
        const iframes = document.querySelectorAll('iframe');
        const arkoseIframe = Array.from(iframes).find(f => f.src.includes('arkoselabs'));
        
        if (arkoseIframe) {
            results.found = true;
            results.src = arkoseIframe.src.substring(0, 150);
            
            // Make it visible
            arkoseIframe.style.visibility = 'visible';
            arkoseIframe.style.opacity = '1';
            
            // Show the container
            const arkoseDiv = document.getElementById('arkose-0');
            if (arkoseDiv) {
                arkoseDiv.style.display = 'block';
                results.containerShown = true;
            }
            
            // Try to access iframe content
            try {
                const iframeDoc = arkoseIframe.contentDocument || arkoseIframe.contentWindow.document;
                if (iframeDoc) {
                    results.iframeBody = iframeDoc.body.innerHTML.substring(0, 500);
                    results.iframeTitle = iframeDoc.title;
                } else {
                    results.iframeError = 'Cannot access iframe (cross-origin?)';
                }
            } catch(e) {
                results.iframeError = e.message;
                
                // Try checking iframe location
                try {
                    results.iframeLocation = arkoseIframe.contentWindow.location.href;
                } catch(e2) {
                    results.iframeLocationError = e2.message;
                }
            }
        } else {
            results.found = false;
        }
        
        return results;
    }""")
    print(f"\n=== Arkose iframe content ===", flush=True)
    print(json.dumps(show_result, indent=2), flush=True)
    
    # Check what the iframe shows now
    time.sleep(2)
    page.screenshot(path="arkose_visible.png")
    
    # Try loading iframe content URL directly
    arkose_url = page.evaluate("""() => {
        const iframes = document.querySelectorAll('iframe');
        const arkoseIframe = Array.from(iframes).find(f => f.src.includes('arkoselabs'));
        return arkoseIframe ? arkoseIframe.src : null;
    }""")
    if arkose_url:
        print(f"\nArkose URL: {arkose_url}", flush=True)
        # Try to navigate to it directly (might load the captcha standalone)
    
    time.sleep(10)
    browser.close()
