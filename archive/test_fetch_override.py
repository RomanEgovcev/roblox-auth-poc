"""Override fetch to modify auth 403 response and inject eligibleMethods."""
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
// Override fetch to intercept auth responses and modify challenge metadata
const originalFetch = window.fetch;
window.fetch = function(...args) {
    return originalFetch.apply(this, args).then(async response => {
        // Clone response to read body
        const url = response.url;
        
        if (url.includes('auth.roblox.com') && url.includes('/v2/login') && response.status === 403) {
            const clone = response.clone();
            
            // Check for challenge headers
            const chalMeta = clone.headers.get('rblx-challenge-metadata');
            
            if (chalMeta) {
                try {
                    // Decode metadata
                    let meta = JSON.parse(atob(chalMeta));
                    
                    // Modify eligibleMethods
                    if (meta.sharedParameters) {
                        meta.sharedParameters.eligibleMethods = ['captcha', 'proofofwork'];
                        meta.sharedParameters.renderNativeChallenge = true;
                    } else {
                        meta.sharedParameters = {eligibleMethods: ['captcha', 'proofofwork'], renderNativeChallenge: true};
                    }
                    
                    // Ensure genericChallengeId exists
                    if (!meta.genericChallengeId && meta.sharedParameters) {
                        meta.genericChallengeId = meta.sharedParameters.genericChallengeId || 'us-captcha-fallback';
                    }
                    
                    const newMeta = btoa(JSON.stringify(meta));
                    console.log('[FETCH_OVERRIDE] Modified eligibleMethods in 403 response');
                    
                    // Create new response with modified headers
                    const modifiedHeaders = new Headers(clone.headers);
                    modifiedHeaders.set('rblx-challenge-metadata', newMeta);
                    
                    // Also add the original response if it was going to be read
                    const body = await clone.text();
                    
                    // Return modified response
                    return new Response(body, {
                        status: response.status,
                        statusText: response.statusText,
                        headers: modifiedHeaders
                    });
                } catch(e) {
                    console.error('[FETCH_OVERRIDE] Error:', e);
                }
            }
        }
        
        return response;
    });
};

// Also override XMLHttpRequest
const originalXHROpen = XMLHttpRequest.prototype.open;
const originalXHRSend = XMLHttpRequest.prototype.send;
const originalXHRSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;

XMLHttpRequest.prototype.open = function(method, url) {
    this.__url = url;
    this.__method = method;
    return originalXHROpen.apply(this, arguments);
};

XMLHttpRequest.prototype.send = function(body) {
    const xhr = this;
    const url = xhr.__url || '';
    
    if (url.includes('auth.roblox.com') && url.includes('/v2/login')) {
        const originalOnLoad = xhr.onload;
        const originalOnReadyState = xhr.onreadystatechange;
        
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4 && xhr.status === 403) {
                // Try to get and modify response headers
                const chalMeta = xhr.getResponseHeader('rblx-challenge-metadata');
                if (chalMeta) {
                    try {
                        let meta = JSON.parse(atob(chalMeta));
                        if (meta.sharedParameters) {
                            meta.sharedParameters.eligibleMethods = ['captcha', 'proofofwork'];
                            meta.sharedParameters.renderNativeChallenge = true;
                        }
                        const newMeta = btoa(JSON.stringify(meta));
                        console.log('[XHR_OVERRIDE] Modified eligibleMethods');
                        
                        // Unfortunately XHR response headers are read-only
                        // So we need a different approach for XHR
                    } catch(e) {}
                }
            }
            
            if (originalOnReadyState) {
                originalOnReadyState.apply(xhr, arguments);
            }
        };
    }
    
    return originalXHRSend.apply(this, arguments);
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
        
        # Check response headers
        chal_type = resp.headers.get('rblx-challenge-type', 'N/A')
        chal_id = resp.headers.get('rblx-challenge-id', 'N/A')
        chal_meta_b64 = resp.headers.get('rblx-challenge-metadata', 'none')
        print(f"[+] Type: {chal_type}", flush=True)
        print(f"[+] Metadata prefix: {chal_meta_b64[:60]}...", flush=True)
        
        # Verify metadata was modified
        if chal_meta_b64 and chal_meta_b64 != 'none':
            try:
                pad = len(chal_meta_b64) % 4
                if pad:
                    chal_meta_b64 += '=' * (4 - pad)
                meta = json.loads(base64.b64decode(chal_meta_b64))
                sp = meta.get('sharedParameters', {})
                print(f"[+] eligibleMethods: {sp.get('eligibleMethods', 'N/A')}", flush=True)
                print(f"[+] renderNative: {sp.get('renderNativeChallenge', 'N/A')}", flush=True)
            except Exception as e:
                print(f"[-] Decode error: {e}", flush=True)
        
    except Exception as e:
        print(f"[-] No auth: {e}", flush=True)
    
    time.sleep(5)
    
    # Check frames (ALL of them)
    frames = page.frames
    arkose = [f for f in frames if 'arkose' in f.url]
    enforcement = [f for f in frames if 'enforcement' in f.url]
    print(f"Frames: {len(frames)}, arkose: {len(arkose)}, enforcement: {len(enforcement)}", flush=True)
    for i, f in enumerate(frames):
        url = f.url[:150]
        if url != 'about:blank':
            print(f"  [{i}] {url}", flush=True)
    
    # Check DOM for challenge elements
    challenge_dom = page.evaluate("""() => {
        const results = {};
        // Check for arkose containers
        const arkoseEls = document.querySelectorAll('[id*=\"arkose\"], [class*=\"arkose\"], [id*=\"funcaptcha\"], [class*=\"funcaptcha\"]');
        results.arkoseElements = Array.from(arkoseEls).map(e => e.tagName + '#' + (e.id||''));
        // Check for challenge modals
        const modalEls = document.querySelectorAll('[class*=\"challenge\"], [id*=\"challenge\"]');
        results.challengeElements = Array.from(modalEls).map(e => e.tagName + '#' + (e.id||'') + '.' + (e.className||'')).slice(0,5);
        return results;
    }""")
    print(f"[*] Challenge DOM: {json.dumps(challenge_dom)[:300]}", flush=True)
    
    page.screenshot(path="fetch_override.png")
    time.sleep(10)
    browser.close()
