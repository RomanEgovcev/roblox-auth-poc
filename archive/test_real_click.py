"""Real user click simulation with full network tracing."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    # Trace ALL requests/responses
    all_reqs = []
    page.on("request", lambda r: all_reqs.append({"url": r.url[:200], "method": r.method, "type": r.resource_type}))
    page.on("response", lambda r: all_reqs.append({"url": r.url[:200], "status": r.status, "method": r.request.method}))
    
    # Also log console
    page.on("console", lambda msg: print(f"  [CONSOLE {msg.type}] {msg.text[:200]}", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Clear log before click
    all_reqs.clear()
    
    print("[*] Performing real click...", flush=True)
    try:
        page.click("#login-button", timeout=5000)
        print("[*] Click done", flush=True)
    except Exception as e:
        print(f"[!] Click failed: {e}", flush=True)
        # Try with force
        try:
            page.click("#login-button", force=True, timeout=5000)
            print("[*] Force click done", flush=True)
        except Exception as e2:
            print(f"[!] Force click failed: {e2}", flush=True)
    
    time.sleep(5)
    
    # Print all network activity
    print("\n=== Network activity after click ===", flush=True)
    for r in all_reqs:
        print(f"  {r.get('method','') or ''} {r['url'][:100]} {r.get('status','') or ''}", flush=True)
    
    # Check for auth specifically
    auth_urls = [r for r in all_reqs if 'auth' in r['url'].lower() or 'login' in r['url'].lower()]
    print(f"\n=== Auth/login related ===", flush=True)
    for r in auth_urls:
        print(f"  {r}", flush=True)
    
    # Check page
    print(f"\nURL: {page.url[:150]}", flush=True)
    
    # Check for the onclick function in page
    print("\n=== Checking f function existence ===", flush=True)
    # We can try to call f by evaluating the button's event handler differently
    f_check = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        const reactKey = Object.keys(btn).find(k => k.startsWith('__reactProps'));
        const onClick = btn[reactKey].onClick;
        
        // onClick is function(e){return f()}
        // Try to get f from the fiber's state
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        
        // Traverse the fiber tree to find where f is stored
        let node = btn[fiberKey];
        let depth = 0;
        while (node && depth < 10) {
            // Check alternate fiber for more info
            if (node.alternate && node.alternate.memoizedState) {
                // try to find f in state
            }
            if (node.memoizedState && node.memoizedState.queue) {
                try {
                    const q = node.memoizedState.queue;
                    if (q.lastRenderedState && typeof q.lastRenderedState === 'function') {
                        return {found: 'lastRenderedState', src: q.lastRenderedState.toString().substring(0, 200)};
                    }
                } catch(e) {}
            }
            node = node.return;
            depth++;
        }
        
        return {note: onClick.toString()};
    }""")
    print(json.dumps(f_check, indent=2), flush=True)
    
    input("Enter to close...")
    browser.close()
