"""Check chrome://extensions via Shadow DOM to see NopeCHA status."""
import os, time, subprocess, json

chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext_path = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

import shutil
if os.path.exists(profile):
    shutil.rmtree(profile)
time.sleep(0.5)

proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions",
     "--show-component-extension-options"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(6)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    # Enable developer mode first
    page.goto("chrome://extensions", wait_until="domcontentloaded")
    time.sleep(3)
    
    # Check if dev mode toggle exists and click it
    result = page.evaluate("""() => {
        const mgr = document.querySelector('extensions-manager');
        if (!mgr) return 'no extensions-manager found';
        const shadow = mgr.shadowRoot;
        if (!shadow) return 'no shadow root';
        const text = shadow.textContent || '';
        // Find nopecha
        const lines = text.split('\\n').filter(l => l.includes('Nope') || l.includes('dknlfm'));
        return {
            hasText: text.length,
            nopechaLines: lines.slice(0, 10),
            sample: text.slice(0, 2000)
        };
    }""")
    print("=== Extensions page ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Also check via the detail view (if extension has errors)
    page.goto(f"chrome://extensions/?id=dknlfmjaanfblgfdfebhijalfmhmjjjo", wait_until="domcontentloaded")
    time.sleep(2)
    result2 = page.evaluate("""() => {
        const mgr = document.querySelector('extensions-manager');
        if (!mgr || !mgr.shadowRoot) return 'no shadow';
        return mgr.shadowRoot.textContent.slice(0, 3000);
    }""")
    print(f"\n=== Extension detail view ===")
    print(result2)

proc.kill()
