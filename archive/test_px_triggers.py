"""Try PX.setChallenge with various configs and explore channels."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[40:120]}", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Explore Events.channels
    channels = page.evaluate("""() => {
        const info = {};
        try {
            const ch = PX.Events.channels;
            info.type = typeof ch;
            if (typeof ch === 'object' && ch !== null) {
                info.keys = Object.keys(ch).slice(0, 30);
                // For each channel, check its structure
                info.details = {};
                for (const k of Object.keys(ch).slice(0, 10)) {
                    try {
                        const v = ch[k];
                        if (typeof v === 'object' && v !== null) {
                            info.details[k] = {
                                keys: Object.keys(v).slice(0, 10),
                                type: typeof v,
                            };
                        } else {
                            info.details[k] = typeof v;
                        }
                    } catch(e) {
                        info.details[k] = 'error: ' + e.message;
                    }
                }
            }
        } catch(e) {
            info.error = e.message;
        }
        return info;
    }""")
    print(f"Events.channels:", flush=True)
    print(json.dumps(channels, indent=2)[:2000], flush=True)
    
    # Try setChallenge with various configs
    print(f"\nTrying PX.setChallenge...", flush=True)
    
    # Try 1: With publicKey
    r1 = page.evaluate("""() => {
        try {
            PX.setChallenge({publicKey: '476068BF-9607-4799-B53D-966BE98E2B81'});
            return 'ok';
        } catch(e) { return 'error: ' + e.message; }
    }""")
    print(f"  setChallenge(publicKey): {r1}", flush=True)
    time.sleep(3)
    
    # Check if anything changed
    r2 = page.evaluate("""() => {
        // Check if any Arkose-related elements appeared
        const scripts = Array.from(document.querySelectorAll('script')).map(s => s.src).filter(s => s.includes('arkoselabs') || s.includes('api.js'));
        const frames = Array.from(document.querySelectorAll('iframe')).map(f => f.src).filter(s => s.includes('arkoselabs') || s.includes('enforcement'));
        return {scripts, frames};
    }""")
    print(f"  After setChallenge: {json.dumps(r2, indent=2)[:500]}", flush=True)
    
    # Try 2: Call trigger on Events to see what happens
    print(f"\nTrying PX.Events.trigger...", flush=True)
    r3 = page.evaluate("""() => {
        try {
            PX.Events.trigger('challenge');
            return 'ok';
        } catch(e) { return 'error: ' + e.message; }
    }""")
    print(f"  trigger('challenge'): {r3}", flush=True)
    time.sleep(2)
    
    # Try 3: Subscribe to challenge event and then trigger
    r4 = page.evaluate("""() => {
        try {
            PX.Events.on('challenge', function(data) {
                console.log('Challenge event received:', JSON.stringify(data));
                window.__challengeData = data;
            });
            return 'subscribed';
        } catch(e) { return 'error: ' + e.message; }
    }""")
    print(f"  Subscribe: {r4}", flush=True)
    
    # Now try to trigger again
    r5 = page.evaluate("""() => {
        try {
            PX.Events.trigger({
                type: 'challenge',
                challengeUrl: 'https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js',
            });
            return 'ok';
        } catch(e) { return 'error: ' + e.message; }
    }""")
    print(f"  trigger with data: {r5}", flush=True)
    time.sleep(5)
    
    # Check frames
    frames = page.frames
    print(f"\nFrames ({len(frames)}):", flush=True)
    for f in frames:
        if 'arkoselabs' in f.url or 'enforcement' in f.url or 'about:blank' not in f.url:
            print(f"  {f.url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
