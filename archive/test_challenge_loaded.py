"""Deep dive into Roblox Challenge module."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    all_requests = []
    page.on("response", lambda r: all_requests.append({"u": r.url[60:150], "s": r.status}))
    page.on("request", lambda r: all_requests.append({"ru": r.url[60:150], "m": r.method}))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Fill form
    page.evaluate(f"""() => {{
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        const u = document.querySelector('input[name="username"]');
        const p = document.querySelector('input[type="password"]');
        if (u) {{ setter.call(u, '{USER}'); u.dispatchEvent(new Event('input', {{bubbles: true}})); }}
        if (p) {{ setter.call(p, '{PASS}'); p.dispatchEvent(new Event('input', {{bubbles: true}})); }}
    }}""")
    time.sleep(1)
    
    # Click login via Playwright
    page.click('button[type="submit"]', timeout=5000)
    print("Clicked login!", flush=True)
    
    # Wait for challenge to load
    time.sleep(5)
    
    # Check if Challenge module is loaded
    challenge_state = page.evaluate("""() => {
        const result = {};
        if (window.Roblox && window.Roblox.Challenge) {
            result.ChallengeLoaded = true;
            result.ChallengeKeys = Object.keys(window.Roblox.Challenge);
            // Check methods
            const methods = {};
            for (const k of Object.keys(window.Roblox.Challenge)) {
                const v = window.Roblox.Challenge[k];
                if (typeof v === 'function') methods[k] = v.toString().substring(0, 300);
                else methods[k] = typeof v;
            }
            result.methods = methods;
        } else {
            result.ChallengeLoaded = false;
        }
        // Check for challenge overlay in DOM
        result.challengeOverlays = [];
        document.querySelectorAll('[class*="challenge" i], [id*="challenge" i]').forEach(el => {
            result.challengeOverlays.push(el.className.substring(0, 100) || el.id.substring(0, 100));
        });
        // Check for visible overlays/modals
        result.visibleModals = [];
        document.querySelectorAll('[class*="modal" i], [class*="overlay" i]').forEach(el => {
            const style = window.getComputedStyle(el);
            if (style.display !== 'none' && style.visibility !== 'hidden') {
                result.visibleModals.push(el.className.substring(0, 100) || el.id.substring(0, 100));
            }
        });
        return result;
    }""")
    print(f"\nChallenge state: {json.dumps(challenge_state, indent=2)}", flush=True)
    
    # If Challenge loaded, try calling getRedemptionToken
    if challenge_state.get('ChallengeLoaded'):
        print("\n  Calling Roblox.Challenge.getRedemptionToken...", flush=True)
        # We need to find the challenge data - let's see how the module works
        # Look for the challenge ID in the page state
        challenge_data = page.evaluate("""() => {
            // Look for challenge data in the module or in expando attributes
            const C = window.Roblox.Challenge;
            // Check if there's a pending challenge
            for (const k of Object.keys(C)) {
                const v = C[k];
                if (v && typeof v === 'object') {
                    return {key: k, value: JSON.stringify(v).substring(0, 500)};
                }
            }
            return {msg: 'no objects found'};
        }""")
        print(f"  Challenge data: {challenge_data}", flush=True)
    
    # Check current URL and page state
    print(f"\nCurrent URL: {page.url}", flush=True)
    
    # Filter challenge-related requests
    chall_reqs = [r for r in all_requests if 'challenge' in str(r).lower() or 'Chall' in str(r).get('u', '')]
    print(f"\nChallenge requests ({len(chall_reqs)}):", flush=True)
    for r in chall_reqs:
        print(f"  {r}", flush=True)
    
    # Check auth POST requests
    auth_posts = [r for r in all_requests if 'auth' in str(r).get('u', '').lower() and r.get('m') == 'POST']
    print(f"\nAuth POSTs ({len(auth_posts)}):", flush=True)
    for r in auth_posts:
        print(f"  {r}", flush=True)
    
    time.sleep(2)
    browser.close()
