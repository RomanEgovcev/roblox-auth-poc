"""Replace PX with pass-through mock to allow auth flow."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

MOCK_PX_JS = r"""
(function() {
    var pxAppId = 'PXbf8PROpW';
    window._pxAppId = pxAppId;
    window._pxVid = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx';
    window._pxUuid = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:true';
    window._pxHostUrl = 'https://collector-PXbf8PROpW.px-cloud.net';
    window._pxJsClientSrc = '/PXbf8PROpW/init.js';
    window._pxFirstPartyEnabled = true;
    
    var pxMock = {
        _pxAppId: pxAppId,
        ClientUuid: function(){return 'mock-uuid'},
        Events: { emit: function(){}, on: function(){}, subscribe: function(){} },
        setChallenge: function(){},
        _px: pxAppId,
        Options: {},
    };
    
    window.pxInit = window.pxInit || function(){};
    window.PX = pxMock;
    window[pxAppId] = pxMock;
    console.log('[MockPX] Loaded');
})();
"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    auth_responses = []
    def track(r):
        if 'auth.roblox' in r.url:
            auth_responses.append({"url": r.url[:120], "status": r.status})
            print(f"[+] Auth: {r.status}", flush=True)
    page.on("response", track)
    
    # Log all responses for debugging
    all_routes = []
    page.on("response", lambda r: all_routes.append(r.url) if 'roblox' in r.url else None)
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            print(f"[*] Replacing PX: {url[:80]}", flush=True)
            route.fulfill(status=200, body=MOCK_PX_JS, content_type='application/javascript')
        elif 'init.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body='', content_type='application/javascript')
        elif 'collector' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body='[]', content_type='text/plain')
        else:
            route.continue_()
    
    page.route("**/*", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    print(f"[*] Page loaded. Routes seen: {[r for r in all_routes if 'auth' in r.lower()]}", flush=True)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    page.click("#login-button", timeout=5000)
    print("[*] Clicked", flush=True)
    
    for i in range(30):
        if auth_responses:
            print(f"[+] Auth at {i}s: {auth_responses[-1]}", flush=True)
            break
        time.sleep(0.5)
    else:
        print(f"[-] No auth in 15s", flush=True)
    
    input("Enter...")
    browser.close()
