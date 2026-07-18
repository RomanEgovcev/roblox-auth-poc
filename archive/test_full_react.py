"""
Full test: Patch cryptoUtil, fill form, call onFormSubmit, and monitor for login POST + challenge.
If PX intercepts and shows challenge, the native lifecycle may complete the login.
"""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("pageerror", lambda err: print(f"[PAGE_ERROR] {err}", flush=True))
    page.on("console", lambda msg: print(f"[CONSOLE] {msg.text[:200]}", flush=True))
    
    # Monitor all POST requests
    posts = []
    def on_request(req):
        if req.method == "POST":
            posts.append({"url": req.url, "headers": dict(req.headers)})
            if "/v2/login" in req.url:
                print(f"\n=== LOGIN POST DETECTED! ===", flush=True)
                print(f"  URL: {req.url}", flush=True)
                h = dict(req.headers)
                for k, v in h.items():
                    if "csrf" in k.lower() or "challenge" in k.lower() or "token" in k.lower():
                        print(f"  {k}: {v}", flush=True)
    page.on("request", on_request)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    print("Page loaded", flush=True)
    
    # Fill credentials
    page.fill('input[name="username"]', "testuser123")
    page.fill('input[name="password"]', "TestPassword123!")
    time.sleep(1)
    
    # Patch cryptoUtil and trigger onFormSubmit
    result = page.evaluate("""async () => {
        const cu = window.CoreRobloxUtilities.cryptoUtil;
        if (!cu) return 'no cryptoUtil';
        
        // Patch generateSecureAuthIntentV2 to return a valid intent
        cu.generateSecureAuthIntentV2 = async function() {
            return JSON.parse('{"clientPublicKey":"MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE3IKczbs0NsRQyHZP8npajBZ9J2AhMpicZzSXkh46szPk5kIK4vVr03_dHHRgIhIT3KILvBpH1n9SDQfVzOnsHA"}');
        };
        
        // Find onFormSubmit
        const key = Object.keys(document.querySelector('#login-base') || document.querySelector('[class*=\"login\"]') || document.body)
            .find(k => k.startsWith('__reactFiber'));
        if (!key) return 'no react fiber';
        
        function walkFibers(fiber, depth, cb) {
            if (!fiber || depth > 15) return;
            cb(fiber, depth);
            if (fiber.child) walkFibers(fiber.child, depth + 1, cb);
            if (fiber.sibling) walkFibers(fiber.sibling, depth, cb);
        }
        
        let found = false;
        const root = document.querySelector('#login-base') || document.querySelector('#react-login-web-app') || document.body;
        const rootFiber = root[key];
        
        walkFibers(rootFiber, 0, (f, d) => {
            if (f.memoizedProps && f.memoizedProps.onFormSubmit && !found) {
                console.log('Found onFormSubmit at depth', d);
                found = true;
                try {
                    f.memoizedProps.onFormSubmit();
                    console.log('onFormSubmit called successfully');
                } catch(e) {
                    console.error('onFormSubmit error:', e);
                }
            }
        });
        return found ? 'onFormSubmit called' : 'not found';
    }""")
    print(f"Result: {result}", flush=True)
    
    # Wait for requests
    time.sleep(8)
    
    login_posts = [p for p in posts if "/v2/login" in p["url"]]
    print(f"\nLogin POSTs detected: {len(login_posts)}", flush=True)
    for p in login_posts:
        print(f"  POST to {p['url']}", flush=True)
        for k, v in p["headers"].items():
            if "csrf" in k.lower() or "challenge" in k.lower() or "token" in k.lower() or "content" in k.lower():
                print(f"    {k}: {v[:80]}", flush=True)
    
    time.sleep(10)
    print(f"\nFinal URL: {page.url}", flush=True)
    
    time.sleep(3)
    browser.close()
