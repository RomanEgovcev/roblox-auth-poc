"""Find and call login function directly from page JS."""
import os, time, subprocess, json

chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

proc = subprocess.Popen(
    [chrome, f"--user-data-dir={profile}", f"--load-extension={ext}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(8)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(5)
    
    # Search for login function in all scripts
    login_func = page.evaluate("""() => {
        // Search window globals
        const found = [];
        for (const key in window) {
            try {
                const val = window[key];
                const str = String(val);
                if (str.includes('auth.roblox.com') || str.includes('v2/login')) {
                    found.push({key: key, type: typeof val, str: str.slice(0, 200)});
                }
            } catch(e) {}
        }
        return found;
    }""")
    print(f"Login functions in window: {json.dumps(login_func, indent=2, default=str)[:1000]}", flush=True)
    
    # Also search all scripts for login URL
    print("\n[*] Searching scripts for login handler...", flush=True)
    handlers = page.evaluate("""() => {
        const results = [];
        document.querySelectorAll('script').forEach(s => {
            const src = s.src || 'inline';
            const text = (s.textContent || s.innerText || '').slice(0, 5000);
            if (text.includes('auth.roblox.com') || text.includes('login-button') || text.includes('v2/login')) {
                const lines = text.split('\\n').filter(l => l.includes('auth.roblox') || l.includes('login-button') || l.includes('v2/login'));
                results.push({src: src.slice(-60), lines: lines.slice(0, 5)});
            }
        });
        return results;
    }""")
    print(f"Results: {json.dumps(handlers, indent=2, default=str)[:2000]}", flush=True)
    
proc.kill()
