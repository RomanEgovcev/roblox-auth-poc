"""Check if eval works in Playwright Chromium."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    # Test eval
    result = page.evaluate("""() => {
        const tests = {};
        try { tests.eval = eval('1+1'); } catch(e) { tests.eval_err = e.message; }
        try { tests.fn = new Function('return 1+1')(); } catch(e) { tests.fn_err = e.message; }
        try { 
            const s = document.createElement('script');
            s.textContent = 'window.__eval_test = 42;';
            document.head.appendChild(s);
            tests.script_inject = window.__eval_test;
        } catch(e) { tests.script_err = e.message; }
        return tests;
    }""")
    print(f"Eval tests: {json.dumps(result, indent=2)}", flush=True)
    
    # Check user agent
    ua = page.evaluate("() => navigator.userAgent")
    print(f"UA: {ua}", flush=True)
    
    # Check Playwright version
    print(f"Browser version: {browser.version}", flush=True)
    
    input("Enter...")
    browser.close()
