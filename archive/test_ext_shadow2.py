"""Check chrome://extensions to see NopeCHA extension status."""
import os, time, subprocess, json

chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext_path = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

import shutil
try:
    if os.path.exists(profile):
        shutil.rmtree(profile, ignore_errors=True)
except:
    pass
time.sleep(1)

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
    
    page.goto("chrome://extensions", wait_until="domcontentloaded")
    time.sleep(4)
    
    result = page.evaluate("""() => {
        const mgr = document.querySelector('extensions-manager');
        if (!mgr || !mgr.shadowRoot) return {error: 'no shadow access'};
        const text = mgr.shadowRoot.textContent || '';
        const nopechaLines = text.split('\\n').filter(l => l.includes('Nope') || l.includes('dknlfm') || l.includes('CAPTCHA'));
        return {
            textLength: text.length,
            nopechaLines: nopechaLines.slice(0, 20),
            textStart: text.slice(0, 3000)
        };
    }""")
    print("=== Extensions page ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))

proc.kill()
