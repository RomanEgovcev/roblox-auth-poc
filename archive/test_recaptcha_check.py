"""Check reCAPTCHA and form validation blockers."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    all_req = []
    page.on("request", lambda r: all_req.append({"u": r.url[:150], "m": r.method, "t": time.time()}))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Check for reCAPTCHA before filling
    recaptcha_before = page.evaluate("""() => ({
        hasGrecaptcha: typeof window.grecaptcha !== 'undefined',
        grecaptchaKeys: window.grecaptcha ? Object.keys(window.grecaptcha).filter(k => !k.startsWith('_')) : [],
        hasRecaptchaWidgets: typeof window.grecaptcha !== 'undefined' && typeof window.grecaptcha.render === 'function',
        recaptchaSiteKeys: typeof window.___grecaptcha_cfg !== 'undefined' ? 
            (window.___grecaptcha_cfg && window.___grecaptcha_cfg.clients ? Object.values(window.___grecaptcha_cfg.clients).map(c => c && c.site_key).filter(Boolean) : []) : [],
    })""")
    print(f"reCAPTCHA before: {json.dumps(recaptcha_before, indent=2)}", flush=True)
    
    # Fill form
    page.fill('#login-username', USER)
    page.fill('#login-password', PASS)
    time.sleep(1)
    
    click_time = time.time()
    page.click('.login-button', timeout=5000)
    print("Clicked!", flush=True)
    
    time.sleep(3)
    
    # Check reCAPTCHA after click
    recaptcha_after = page.evaluate("""() => ({
        hasGrecaptcha: typeof window.grecaptcha !== 'undefined',
        recaptchaWidgets: typeof window.___grecaptcha_cfg !== 'undefined' && window.___grecaptcha_cfg.clients ? 
            Object.entries(window.___grecaptcha_cfg.clients).map(([id, c]) => ({id, site_key: c.site_key, hasWidgets: Object.keys(c.widgets || {}).length})) : [],
        recaptchaResponse: document.querySelector('#g-recaptcha-response')?.value,
    })""")
    print(f"reCAPTCHA after: {json.dumps(recaptcha_after, indent=2)}", flush=True)
    
    # Check Google recaptcha requests
    recaptcha_req = [r for r in all_req if 'google.com/recaptcha' in r['u'] or 'gstatic.com/recaptcha' in r['u'] or 'recaptcha' in r['u'].lower()]
    print(f"\nreCAPTCHA requests ({len(recaptcha_req)}):", flush=True)
    for r in recaptcha_req:
        dt = round(r.get('t', 0) - click_time, 2) if r.get('t') else 0
        print(f"  [{dt:+.2f}s] {r['u'][:120]}", flush=True)
    
    # Check if there were any validation errors on the form
    val_errors = page.evaluate("""() => {
        const errs = [];
        document.querySelectorAll('[class*="error"], [class*="validation"], [class*="warning"]').forEach(el => {
            if (el.offsetParent !== null && el.textContent.trim()) {
                errs.push(el.textContent.trim().substring(0, 100));
            }
        });
        // Check for recaptcha error
        const recaptchaErr = document.querySelector('[class*="recaptcha-error"], [data-component="recaptcha"]');
        return {errors: errs, recaptchaError: recaptchaErr ? recaptchaErr.textContent.trim().substring(0, 100) : null};
    }""")
    print(f"\nValidation errors: {json.dumps(val_errors, indent=2)}", flush=True)
    
    time.sleep(2)
    browser.close()
