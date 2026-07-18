"""Check what PX/Analytics scripts are actually loaded on the login page."""
import os, time, json, sys

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled', '--disable-web-security']
    )
    page = browser.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    print("[1] Page loaded...", flush=True)
    time.sleep(10)
    
    # Check all scripts loaded
    scripts = page.evaluate("""() => {
        return Array.from(document.scripts).slice(0, 30).map(s => ({
            src: (s.src || '').substring(0, 200),
            id: s.id,
            type: s.type,
            innerLen: (s.text || '').length
        }));
    }""")
    print(f"\n=== Scripts ({len(scripts)}) ===", flush=True)
    for s in scripts:
        if s['src']:
            print(f"  SRC: {s['src']}", flush=True)
        elif s['id']:
            print(f"  ID: {s['id']} ({s['innerLen']} chars)", flush=True)
    
    # Check for specific PX/captcha variables
    vars = page.evaluate("""() => {
        const result = {};
        const check = ['_px', '_px3', 'PX', 'PBot', 'PerimeterX', 'captcha', 'funCaptcha', 'FunCaptcha', 'Arkose', 'arkose', 'Challenge'];
        check.forEach(k => {
            try {
                result[k] = typeof eval(k);
            } catch(e) {
                result[k] = 'undefined';
            }
        });
        return result;
    }""")
    print(f"\n=== Variables ===", flush=True)
    for k, v in vars.items():
        print(f"  {k}: {v}", flush=True)
    
    # Check login form structure
    form = page.evaluate("""() => {
        const form = document.querySelector('#login-form') || document.querySelector('form');
        if (!form) return {error: 'no form'};
        return {
            action: form.action,
            method: form.method,
            id: form.id,
            inputs: Array.from(form.querySelectorAll('input')).map(i => ({name: i.name, type: i.type, id: i.id})),
            buttons: Array.from(form.querySelectorAll('button')).map(b => ({id: b.id, text: b.textContent.substring(0, 50)})),
        };
    }""")
    print(f"\n=== Login form ===", flush=True)
    print(f"  {json.dumps(form, indent=2)[:1000]}", flush=True)
    
    browser.close()
