"""Find and call the form's onSubmit React handler to submit login."""
import os, time, json, sys, re

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(2)
    
    # Find form's onSubmit handler
    print("[1] Finding form's React onSubmit...", flush=True)
    form_handler = page.evaluate("""() => {
        const form = document.getElementById('login-form');
        if (!form) return {error: 'form not found'};
        
        // Find React fiber
        const fiberKey = Object.keys(form).find(k => k.startsWith('__reactFiber'));
        if (!fiberKey) return {error: 'no fiber'};
        
        let fiber = form[fiberKey];
        let depth = 0;
        while (fiber && depth < 50) {
            const props = fiber.memoizedProps;
            if (props?.onSubmit) {
                return {
                    depth, fiberTag: fiber.tag,
                    typeStr: (typeof fiber.type === 'function' ? fiber.type.toString().substring(0, 200) : String(fiber.type)),
                    onSubmit: props.onSubmit.toString().substring(0, 500),
                    action: props.action,
                    method: props.method,
                };
            }
            if (props?.id === 'login-form') {
                return {formFound: true, depth, props: Object.keys(props).slice(0, 20), hasOnSubmit: !!props.onSubmit};
            }
            fiber = fiber.return;
            depth++;
        }
        return {error: 'not found', depth};
    }""")
    print(f"  {json.dumps(form_handler)[:600]}", flush=True)
    
    # Also try to find the submit handler via the form's reactProps
    print("\n[2] Trying form.requestSubmit...", flush=True)
    result = page.evaluate("""async () => {
        try {
            const form = document.getElementById('login-form');
            if (!form) return {error: 'form not found'};
            form.requestSubmit();
            return {ok: true};
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"  requestSubmit: {json.dumps(result)[:200]}", flush=True)
    time.sleep(5)
    
    # Check what happened
    print(f"\n  URL: {page.url[:200]}", flush=True)
    print(f"  Frames:", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"    [{fi}] {f.url[:200]}", flush=True)
    
    # Check enforcement for game-core
    for f in page.frames:
        if 'game-core' in f.url:
            state = f.evaluate("""() => ({
                bodyLen: document.body?.innerHTML?.length || 0,
                bodyPreview: document.body?.innerHTML?.substring(0, 300) || '',
            })""")
            print(f"\n  Game-core: {json.dumps(state)[:400]}", flush=True)
            break
    
    time.sleep(10)
    browser.close()
