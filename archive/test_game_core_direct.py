"""Capture game-core URL and load it directly."""
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
    
    game_core_urls = []
    
    def track_urls(response):
        url = response.url
        if 'game-core/index.html' in url or 'game_core_bootstrap' in url:
            game_core_urls.append(url)
            print(f"[+] Game-core: {url[:200]}", flush=True)
    
    page.on("response", track_urls)
    
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
    
    # Find game-core URL
    game_core_url = None
    for url in game_core_urls:
        if 'game-core/index.html' in url:
            game_core_url = url
            break
    
    if game_core_url:
        print(f"[+] Loading game-core: {game_core_url[:200]}", flush=True)
        
        # Navigate to game-core directly
        gc_page = browser.new_page()
        gc_page.goto(game_core_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)
        
        # Screenshot game-core
        gc_page.screenshot(path="game_core_direct.png")
        
        # Check game-core content
        gc_content = gc_page.evaluate("""() => {
            return {
                title: document.title,
                url: window.location.href.substring(0, 200),
                bodyHTML: document.body.innerHTML.substring(0, 2000),
                scripts: Array.from(document.scripts).map(s => s.src).filter(Boolean).slice(0,5),
                iframes: Array.from(document.querySelectorAll('iframe')).map(f => f.src).filter(Boolean).slice(0,5)
            };
        }""")
        print(f"[+] Game-core content: {json.dumps(gc_content, indent=2)[:2000]}", flush=True)
        
        # Wait and check for captcha elements
        for i in range(20):
            gc_state = gc_page.evaluate("""() => {
                const canvases = document.querySelectorAll('canvas');
                const imgs = document.querySelectorAll('img');
                const iframes = document.querySelectorAll('iframe');
                return {
                    canvases: canvases.length,
                    images: imgs.length,
                    iframes: iframes.length,
                    bodyLen: document.body?.innerHTML?.length || 0,
                    iframeSrc: iframes.length > 0 ? iframes[0].src : ''
                };
            }""")
            if gc_state.get('canvases', 0) > 0 or gc_state.get('images', 0) > 5:
                print(f"[+] Captcha game elements found at {i}s!", flush=True)
                print(f"  State: {json.dumps(gc_state)}", flush=True)
                gc_page.screenshot(path=f"game_core_captcha_{i}.png")
                break
            time.sleep(1)
        else:
            print(f"[-] No captcha after 20s. Final state: {json.dumps(gc_state)}", flush=True)
        
        time.sleep(10)
        browser.close()
    else:
        print("[-] No game-core URL found. Available URLs:", flush=True)
        for url in game_core_urls:
            print(f"  {url[:150]}", flush=True)
        time.sleep(10)
        browser.close()
