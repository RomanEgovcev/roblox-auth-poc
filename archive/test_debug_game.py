"""Debug: check enforcement DOM and game-core message handlers."""
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
time.sleep(6)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    auth_responses = []
    page.on("response", lambda r: auth_responses.append({"url": r.url[:200], "status": r.status}))
    
    page.click("#login-button")
    print("[*] Submitted", flush=True)
    
    enf = None
    game = None
    for i in range(90):
        for f in page.frames:
            if 'enforcement' in f.url and 'roblox.com' in f.url:
                enf = f
            if 'game-core' in f.url:
                game = f
        if enf and game:
            print(f"[+] Both frames at {i}s", flush=True)
            break
        time.sleep(1)
    else:
        print("[-] Not found", flush=True)
        proc.kill(); exit(1)
    
    time.sleep(2)
    
    # Check enforcement DOM - what's inside #app?
    app_content = enf.evaluate("""() => {
        const app = document.getElementById('app');
        if (!app) return 'no app div';
        return {
            childCount: app.children.length,
            html: app.innerHTML.slice(0, 3000),
            childTags: Array.from(app.children).map(c => c.tagName)
        };
    }""")
    print(f"Enforcement #app: {json.dumps(app_content, indent=2, default=str)}", flush=True)
    
    # Check enforcement full DOM tree
    dom_tree = enf.evaluate("""() => {
        function tree(el, depth) {
            if (depth > 3) return el.tagName + '...';
            const children = Array.from(el.children).map(c => tree(c, depth+1));
            return {tag: el.tagName, id: el.id, class: el.className?.slice(0, 50), children: children};
        }
        return tree(document.body, 0);
    }""")
    print(f"Enforcement DOM tree: {json.dumps(dom_tree, indent=2, default=str)[:2000]}", flush=True)
    
    # Check game-core message listeners
    # Try to find what messages game-core accepts
    postmsg = game.evaluate("""() => {
        const orig = window.postMessage;
        let calls = [];
        window.postMessage = function(msg, target) {
            calls.push({msg: JSON.stringify(msg).slice(0, 200), target: target});
            // Don't break original
            return orig.call(window, msg, target);
        };
        return 'hooked';
    }""")
    print(f"PostMessage hook: {postmsg}", flush=True)
    
    # Check game-core events
    check = game.evaluate("""() => {
        return {
            reactRoot: !!document.querySelector('#root')._reactRootContainer,
            styledPresent: !!document.querySelector('style[data-styled]'),
            canvasCount: document.querySelectorAll('canvas').length,
            scripts: Array.from(document.scripts).map(s => ({src: s.src?.slice(-40), text: s.text?.slice(0, 100)}))
        };
    }""")
    print(f"Game-core state: {json.dumps(check, indent=2, default=str)}", flush=True)
    
    # Check game-core main.js loaded?
    js_loaded = game.evaluate("""() => {
        return {
            hasWebpack: typeof __webpack_nonce__ !== 'undefined',
            scriptCount: document.scripts.length,
            lastScript: document.scripts[document.scripts.length-1]?.src?.slice(-40) || 'none',
            bodyChildren: document.body.children.length,
            rootHtml: document.getElementById('root')?.innerHTML?.slice(0, 500) || 'empty'
        };
    }""")
    print(f"JS loaded: {json.dumps(js_loaded, indent=2, default=str)}", flush=True)
    
    # Now try triggering game start by posting a message to game-core
    # Listen for console output from game-core
    print("\n[*] Trying to trigger game start...", flush=True)
    messages = []
    page.on("console", lambda msg: messages.append({"text": msg.text[:200], "type": msg.type}))
    
    # Send various possible start messages
    test_msgs = [
        {"type": "start", "session": "test_session"},
        {"type": "challenge", "token": "test_token", "session": "test"},
        {"event": "start", "payload": {"session": "test", "type": "match_game"}},
    ]
    
    for mi, msg in enumerate(test_msgs):
        try:
            enf.evaluate(f"""() => {{
                const frame = document.querySelector('iframe') || document.getElementById('app')?.querySelector('iframe');
                if (frame && frame.contentWindow) {{
                    frame.contentWindow.postMessage({json.dumps(msg)}, '*');
                    return 'sent to iframe';
                }}
                return 'no iframe found';
            }}""")
        except Exception as e:
            print(f"  msg {mi}: {e}", flush=True)
        time.sleep(0.5)
    
    # Also try sending directly via window from parent
    try:
        game.evaluate(f"""() => {{
            window.dispatchEvent(new CustomEvent('message', {{detail: {json.dumps({"type": "init", "session": "test"})}}}));
            return 'dispatched';
        }}""")
    except Exception as e:
        print(f"  direct dispatch: {e}", flush=True)
    
    time.sleep(3)
    
    # Check if anything changed
    canvas_after = game.evaluate("""() => {
        const c = document.querySelector('canvas');
        return c ? {w: c.width, h: c.height} : false;
    }""")
    print(f"Canvas after triggers: {canvas_after}", flush=True)
    
    # Check for any new frames or DOM changes
    dom_after = game.evaluate("""() => {
        const root = document.getElementById('root');
        return root?.innerHTML?.slice(0, 500) || 'no root';
    }""")
    print(f"Root after: {dom_after}", flush=True)
    
    console_msgs = [m for m in messages if 'error' in m['text'].lower() or 'log' in m['text'].lower() or 'start' in m['text'].lower()]
    if console_msgs:
        print(f"Console messages: {console_msgs}", flush=True)
    
    time.sleep(5)
    proc.kill()
