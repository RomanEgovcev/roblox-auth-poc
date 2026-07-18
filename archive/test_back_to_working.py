"""Back to the working approach: add_init_script + page.route for PX only."""
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
            console.log('[FETCH] INTERCEPTING AUTH!');
            const clone = response.clone();
            const chalMeta = clone.headers.get('rblx-challenge-metadata');
            console.log('[FETCH] Challenge header:', !!chalMeta);
            if (chalMeta) {
                try {
                    let meta = JSON.parse(atob(chalMeta));
                    console.log('[FETCH] Meta eligibleMethods:', meta.sharedParameters?.eligibleMethods);
                    if (meta.sharedParameters) {
                        meta.sharedParameters.eligibleMethods = ['captcha', 'proofofwork'];
                        meta.sharedParameters.renderNativeChallenge = true;
                    }
                    const newMeta = btoa(JSON.stringify(meta));
                    const modHeaders = new Headers(clone.headers);
                    modHeaders.set('rblx-challenge-metadata', newMeta);
                    const body = await clone.text();
                    console.log('[FETCH] AUTH MODIFIED SUCCESS');
                    return new Response(body, {status: response.status, statusText: response.statusText, headers: modHeaders});
                } catch(e) { console.log('[FETCH] Error:', e); }
            }
        }
        return response;
    });
};
console.log('[FETCH] Override installed');
"""

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.add_init_script(FETCH_OVERRIDE)
    
    logs = []
    page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text[:300]}"))
    
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
    
    time.sleep(8)
    
    # Check enforcement state AND console logs for fetch override
    state = page.evaluate("""() => {
        const r = {};
        r.arkose0 = document.getElementById('arkose-0') ? {
            html: document.getElementById('arkose-0').innerHTML.substring(0, 100),
            iframes: document.querySelectorAll('#arkose-0 iframe').length
        } : 'missing';
        r.arkoseScript = document.getElementById('arkose-script-0') ? 'exists' : 'missing';
        r.genericChallenge = document.getElementById('generic-challenge-container-proofofwork') ? 'exists' : 'missing';
        r.challengeScript = document.querySelector('script[data-rblx-challenge]') ? 'exists' : 'missing';
        r.PX = typeof window._px;
        r.PX_setChallenge = typeof window.PX?.setChallenge;
        r.ph = window.ph;
        r.oC = typeof window.oC;
        return r;
    }""")
    print(f"\n=== State ===", flush=True)
    print(json.dumps(state, indent=2), flush=True)
    
    # Show FETCH-related logs
    print(f"\n=== FETCH logs ===", flush=True)
    for log in logs:
        if '[FETCH]' in log:
            print(f"  {log}", flush=True)
    
    # Show error/PX logs
    print(f"\n=== Error/PX logs ===", flush=True)
    for log in logs:
        lower = log.lower()
        if any(k in lower for k in ['error', 'px', 'challenge', 'arkose']):
            print(f"  {log}", flush=True)
    
    page.screenshot(path="back_to_working.png")
    
    time.sleep(5)
    browser.close()
