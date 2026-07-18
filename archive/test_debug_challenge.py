"""Debug: check challenge metadata and enforcement creation."""
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
console.log('[FETCH] Override installed');
const originalFetch = window.fetch;
window.fetch = function(...args) {
    console.log('[FETCH] Called:', args[0]);
    return originalFetch.apply(this, arguments).then(async response => {
        const url = response.url;
        console.log('[FETCH] Response:', url.substring(0,100), response.status);
        if (url.includes('auth.roblox.com') && url.includes('/v2/login') && response.status === 403) {
            const clone = response.clone();
            const chalMeta = clone.headers.get('rblx-challenge-metadata');
            console.log('[FETCH] Challenge header:', chalMeta ? chalMeta.substring(0,100) : 'MISSING');
            if (chalMeta) {
                try {
                    let meta = JSON.parse(atob(chalMeta));
                    console.log('[FETCH] Meta before:', JSON.stringify(meta).substring(0, 300));
                    if (meta.sharedParameters) {
                        meta.sharedParameters.eligibleMethods = ['captcha', 'proofofwork'];
                        meta.sharedParameters.renderNativeChallenge = true;
                    }
                    console.log('[FETCH] Meta after:', JSON.stringify(meta).substring(0, 300));
                    const newMeta = btoa(JSON.stringify(meta));
                    const modHeaders = new Headers(clone.headers);
                    modHeaders.set('rblx-challenge-metadata', newMeta);
                    const body = await clone.text();
                    console.log('[FETCH] Response modified successfully');
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
    
    # Capture console logs
    logs = []
    page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text[:200]}"))
    
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
    
    time.sleep(5)
    
    # Print relevant console logs
    print(f"\n=== Console logs (last 30) ===", flush=True)
    for log in logs[-30:]:
        print(f"  {log}", flush=True)
    
    # Check challenge state on page
    challenge_state = page.evaluate("""() => {
        const r = {};
        
        // Check challenge metadata from rblx-challenge-* elements
        const script = document.querySelector('script[data-rblx-challenge]');
        if (script) {
            r.challengeScript = {
                id: script.getAttribute('data-rblx-challenge'),
                type: script.getAttribute('data-rblx-challenge-type'),
                metadata: script.getAttribute('data-rblx-challenge-metadata')?.substring(0, 200)
            };
        }
        
        // Check Challenge.js state
        r.challengeJS_exists = typeof window.challengePromise !== 'undefined';
        
        // Check PX state
        r.PX_exists = typeof window._px !== 'undefined';
        r.PX_hasGetEnforcement = typeof window._px?.getEnforcement === 'function';
        r.PX_hasSetChallenge = typeof window._px?.setChallenge === 'function';
        
        // DOM check
        r.arkose0 = document.getElementById('arkose-0') ? {
            innerHTML_len: document.getElementById('arkose-0').innerHTML.length,
            iframes: document.querySelectorAll('#arkose-0 iframe').length,
            children: document.getElementById('arkose-0').childElementCount
        } : null;
        
        r.arkoseScript0 = document.getElementById('arkose-script-0') ? {
            src: document.getElementById('arkose-script-0')?.src?.substring(0, 150),
            text_len: document.getElementById('arkose-script-0')?.text?.length || 0
        } : null;
        
        r.genericChallenge = document.getElementById('generic-challenge-container-proofofwork') ? {
            style_display: document.getElementById('generic-challenge-container-proofofwork').style.display
        } : null;
        
        // Check Challenge.js variables
        if (window.oC) r.oC_type = typeof window.oC;
        if (window.ph !== undefined) r.ph = window.ph;
        
        return r;
    }""")
    print(f"\n=== Challenge state ===", flush=True)
    print(json.dumps(challenge_state, indent=2), flush=True)
    
    page.screenshot(path="debug_challenge.png")
    
    time.sleep(5)
    browser.close()
