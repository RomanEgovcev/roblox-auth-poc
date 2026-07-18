"""Get full PX challenge response with all details."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Get full response including all headers and cookies
    result = page.evaluate("""async () => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'x-csrf-token': 'fetch'
            },
            body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
        });
        return {
            status: r.status,
            headers: Object.fromEntries([...r.headers.entries()]),
            text: await r.text()
        };
    }""")
    
    print(f"Status: {result['status']}", flush=True)
    print(f"Headers: {json.dumps(result['headers'], indent=2)}", flush=True)
    print(f"Body: {result['text']}", flush=True)
    
    # Also check cookies
    cookies = context.cookies()
    px_cookies = [c for c in cookies if '_px' in c['name'] or 'px' in c['name'].lower()]
    print(f"\nPX cookies: {json.dumps(px_cookies, indent=2)}", flush=True)
    
    input("Enter...")
    browser.close()
