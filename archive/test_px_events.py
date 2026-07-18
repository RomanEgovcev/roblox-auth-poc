"""Explore PX.setChallenge and Events API deeply."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[40:100]}", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Explore PX.Events
    px_events = page.evaluate("""() => {
        const info = {};
        try {
            const events = PX.Events;
            info.Events_type = typeof events;
            
            // Get all keys (own + prototype chain)
            const allKeys = [];
            for (const k in events) {
                allKeys.push(k);
            }
            info.Events_keys = allKeys.slice(0, 30);
            
            // Get own property keys
            info.Events_ownKeys = Object.getOwnPropertyNames(events).slice(0, 30);
            
            // Check methods
            const methods = {};
            for (const k of Object.getOwnPropertyNames(events)) {
                try {
                    const v = events[k];
                    if (typeof v === 'function') {
                        methods[k] = 'function(' + v.length + ' params)';
                        if (k === 'on') {
                            // Check Events.on method
                            methods[k + '_desc'] = v.toString().substring(0, 200);
                        }
                    } else {
                        methods[k] = typeof v;
                    }
                } catch(e) {}
            }
            info.Events_methods = methods;
            
            // Check on/off/emit
            info.has_on = typeof events.on === 'function';
            info.has_off = typeof events.off === 'function';
            info.has_emit = typeof events.emit === 'function';
            info.has_trigger = typeof events.trigger === 'function';
            
        } catch(e) {
            info.Events_error = e.message;
        }
        return info;
    }""")
    print(f"PX.Events:", flush=True)
    print(json.dumps(px_events, indent=2)[:2000], flush=True)
    
    # Try to stringify PX.setChallenge to understand it
    set_challenge_src = page.evaluate("""() => {
        try {
            const src = PX.setChallenge.toString();
            return src.substring(0, 2000);
        } catch(e) {
            return 'error: ' + e.message;
        }
    }""")
    print(f"\nPX.setChallenge source:", flush=True)
    print(set_challenge_src, flush=True)
    
    # Check PX.Events.on for challenge events
    px_events_on_src = page.evaluate("""() => {
        try {
            const src = PX.Events.on.toString();
            return src.substring(0, 1000);
        } catch(e) {
            return 'error: ' + e.message;
        }
    }""")
    print(f"\nPX.Events.on source:", flush=True)
    print(px_events_on_src, flush=True)
    
    # Check if there are any registered event listeners
    px_listeners = page.evaluate("""() => {
        const info = {};
        try {
            // Check if PX has a listener registry
            for (const k in PX) {
                try {
                    const v = PX[k];
                    if (typeof v === 'object' && v !== null) {
                        const ownKeys = Object.getOwnPropertyNames(v);
                        if (ownKeys.length > 5) {
                            info[k + '_ownKeys'] = ownKeys.slice(0, 20);
                        }
                    }
                } catch(e) {}
            }
        } catch(e) {
            info.error = e.message;
        }
        return info;
    }""")
    print(f"\nPX internal:", flush=True)
    print(json.dumps(px_listeners, indent=2)[:1000], flush=True)
    
    time.sleep(2)
    browser.close()
