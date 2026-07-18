"""Listen to PX Events and explore risk channel."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Listen to risk channel and log all events
    results = page.evaluate("""() => {
        const out = {};
        try {
            // Listen to 'risk' channel
            PX.Events.on('risk', function(data) {
                const key = 'risk_event_' + Date.now();
                window[key] = JSON.stringify(data);
                out[key] = data;
                console.log('Risk event:', data);
            });
            
            // List all event names from subscribe
            out.listening = 'ok';
        } catch(e) {
            out.error = e.message;
        }
        return out;
    }""")
    print(f"Listener set up: {json.dumps(results)[:200]}", flush=True)
    
    # Check if there's a way to get all registered channels
    channels_detail = page.evaluate("""() => {
        const info = {};
        try {
            const ch = PX.Events.channels;
            info.keys = Object.keys(ch);
            for (const k of info.keys) {
                const v = ch[k];
                info[k + '_keys'] = Object.keys(v).slice(0, 20);
                // Check first item
                const firstKey = Object.keys(v)[0];
                if (firstKey) {
                    const item = v[firstKey];
                    info[k + '_sample'] = {
                        keys: Object.keys(item).slice(0, 10),
                        fn: typeof item.fn === 'function' ? item.fn.toString().substring(0, 200) : typeof item.fn,
                    };
                }
            }
        } catch(e) {
            info.error = e.message;
        }
        return info;
    }""")
    print(f"\nChannels detail:", flush=True)
    print(json.dumps(channels_detail, indent=2)[:2000], flush=True)
    
    # Check PX prototype for hidden methods
    px_proto = page.evaluate("""() => {
        const info = {};
        try {
            const proto = Object.getPrototypeOf(PX);
            info.proto_keys = Object.getOwnPropertyNames(proto).slice(0, 30);
            
            // Check all enumerable properties
            const allProps = {};
            for (const k in PX) {
                try {
                    const v = PX[k];
                    allProps[k] = typeof v === 'function' ? 'fn' : typeof v;
                } catch(e) {}
            }
            info.all_props = allProps;
        } catch(e) {
            info.error = e.message;
        }
        return info;
    }""")
    print(f"\nPX proto:", flush=True)
    print(json.dumps(px_proto, indent=2)[:1000], flush=True)
    
    # Also check Roblox Captcha module  
    roblox_captcha = page.evaluate("""() => {
        const info = {};
        
        // Check RobloxCaptcha or similar
        for (const k of Object.keys(window)) {
            if (k.toLowerCase().includes('captcha') || k.toLowerCase().includes('funcaptcha')) {
                info[k] = typeof window[k];
            }
        }
        
        return info;
    }""")
    print(f"\nRoblox Captcha:", flush=True)
    print(json.dumps(roblox_captcha, indent=2)[:500], flush=True)
    
    time.sleep(5)
    browser.close()
