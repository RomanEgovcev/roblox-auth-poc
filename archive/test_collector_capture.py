"""Intercept PX collector, return challenge response to force enforcement."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")
patched = patched.replace("new EvalError", "new Error")

# A real collector response from earlier capture
REAL_COLLECTOR_RESPONSE = '{"do":null,"ob":"Pd8fS55VjGkV3B25BZRL/rpqWfoT+Q/AB+CRlg/QBz65E2iXOB7ZRLJMh1DNKcRiyNKGBhy48Kly1pVD9pW0HBoSURmfaYCF/ZYCuVRgXFTXlLOL17YkfOX5hkQ+/bFPExC8Aks3hDDZWmQPPAizsXOFzqM3HqVBc/GaFs+RoEix0QY0NQiOsMW9I5s4yE62RqJVdG9GW9V4hynV8PkftBrqX3Yy9DSXm4G7JTFAro5B5CWNfC7k06Hf5t8PJ7KFOOle0d21sPX5jZokGzKZNLLvB+KSz2BqWzG0K89N3xTu/KwbuOYtcnrfsCkS+qFxSM+GQlx8+JRs/H2FnB+S7Z3U9BxS7c2OZQ+vTcewEii/xMyc2BKGZ7vYkC8kASwSTU9Idm07/mRPL0BhEZW6c4wY1PG2Nl8OxkG1p9fctGtPt2w7+LCEiPQlq9XQj4eG/o/pnNoRXPE1hFHMpqJCfQ0qQY/QGjtLjlhlyp7wAsLC/99M53G/HGkGr53UD8M7VlyQKXbCSt8BMfGFHZfHkv3HdTkFgu+n98AXEOg29HQ/vnOXNGNqs7cLThb1zWqS+0NBcq6q2CGL8NGMs7PVg42dlHXAtd4O4JAr5f4hYLtJKlMLF5CahM4u8f5D2t4Fx35/0Y3jPXSpFdHDcAxv4WrtU73z1CdwZ9nOkCDWrZ3+8htRfRSCrr5vj4W86yZFGQvBcYFfydWYvlB6jQN1BJ/AngTNypONh9Dms1Mh/m6Hd54YDEbfh0/VJmgjD63P2xACgDmy7n9b4zM0ISMBYH0CCFPEvMv5RoWDHs2iJe8YVI4bNL8R+VySrV+Z/xOhM+xwHAzMfMjLfPZE9DzkyQF94GB2dJb2M/KRfkm+6AOSY7lxhkLvtqN/CvM7aZxMHUwQ7jqLx0Z5tAXyRNEf24EKTjkprWRvwhkfDFB2Jo/UyBBHGdq6DZRQ7sQCZBivG9w45eYRo3GUh+dF3USLJkZnEuqC4RI/cEeLQK0Zh+lISD5IsrLGXPMIBgq/32FBE3L8/qGzFNwMtRAVqRkCCNxxgJasTbEa06ruUMR6NOcYjQNhLXl0L76tM7HCQ0rAEiJNtAeO4Z+pV2ssbqonAOl11Nx05J1XHx9s+bq+FbyWLPvHFMpkWN8iPZT7N/m+0yFbGlOWMt2N7CB1F7O83qIoUQlKJ9zh+fKQk1bFMi5Fq/0EGh+jPXPmQLwomP7Fk3AiQrEJP3C8GL2XhTvFEbkFYxOm5YOGiFF0OLI7C8HzK4tYLOO3ox+8W+5vF4TvOsHf3FOr80vTga5Ay62Kvj8AxXqbRqA3qSoW9CQ3Rpk8hZnQhLeNNqXqKEpPH/LsVp59uIsbcf7SVJMFBQrqnhWNilKhXyqUfWBPA/NrJc4f8wJDsZxxQ6q05GmQJ2LQDjCN8kGOqyqA4Pz6VLLeJgLkAWV5LKD5MK0AvclFmfEK6p8IhQY="}'

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    
    collector_responses = []
    
    def track_resp(r):
        if 'collector-pxbf8propw' in r.url:
            try:
                body = r.text()
                if body:
                    collector_responses.append({"url": r.url, "body": body[:200]})
            except:
                pass
    
    page.on("response", track_resp)
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        elif 'collector-pxbf8propw' in url and 'collector' in url:
            # Return real response (don't modify)
            route.continue_()
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    
    try:
        with page.expect_response(
            lambda r: 'auth.roblox.com' in r.url and '/v2/login' in r.url,
            timeout=15000
        ) as response_info:
            page.click("#login-button", timeout=5000)
        
        resp = response_info.value
        print(f"[+] Auth: {resp.status}", flush=True)
    except Exception as e:
        print(f"[-] No auth: {e}", flush=True)
    
    time.sleep(3)
    
    print(f"\n=== Collector responses ({len(collector_responses)}) ===", flush=True)
    for cr in collector_responses:
        print(f"  Body: {cr['body']}", flush=True)
    
    # Check for enforcement frames
    frames = page.frames
    game_core = sum(1 for f in frames if 'game-core' in f.url or 'arkose' in f.url)
    print(f"Frames: {len(frames)}, game-core/arkose: {game_core}", flush=True)
    
    page.screenshot(path="collector_check.png")
    time.sleep(10)
    browser.close()
