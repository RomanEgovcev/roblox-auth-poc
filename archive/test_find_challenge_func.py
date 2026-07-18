"""Search Roblox JS for PX/challenge handling functions."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    # Listen for console to capture logs
    logs = []
    page.on("console", lambda msg: logs.append({"type": msg.type, "text": msg.text[:500]}))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    
    # Search for challenge-related functions
    funcs = page.evaluate("""() => {
        const results = {};
        
        // Search window for challenge-related functions
        const keys = Object.keys(window);
        const challengeKeys = keys.filter(k => 
            k.toLowerCase().includes('challenge') || 
            k.toLowerCase().includes('captcha') || 
            k.toLowerCase().includes('enforcement') ||
            k.toLowerCase().includes('px') ||
            k.toLowerCase().includes('arkose')
        );
        results.windowKeys = challengeKeys;
        
        // Search window.Roblox for challenge stuff
        if (window.Roblox) {
            const rKeys = Object.keys(window.Roblox);
            const challengeRKeys = rKeys.filter(k => 
                k.toLowerCase().includes('challenge') || 
                k.toLowerCase().includes('captcha') || 
                k.toLowerCase().includes('enforcement') ||
                k.toLowerCase().includes('px') ||
                k.toLowerCase().includes('arkose')
            );
            results.RobloxKeys = challengeRKeys;
            
            // Check Roblox.Challenge
            if (window.Roblox.Challenge) {
                results.Challenge = Object.keys(window.Roblox.Challenge);
            }
        }
        
        // Check for setupEnforcement
        results.setupEnforcement = typeof window.setupEnforcement !== 'undefined';
        results.setupEnforcement0 = typeof window.setupEnforcement0 !== 'undefined';
        
        // Check for generic challenge container
        const container = document.getElementById('generic-challenge-container-proofofwork');
        results.hasContainer = !!container;
        if (container) {
            results.containerHTML = container.innerHTML.substring(0, 500);
            results.containerVisible = container.style.display !== 'none';
        }
        
        return results;
    }""")
    print("Functions found:", flush=True)
    print(json.dumps(funcs, indent=2), flush=True)
    
    # Now submit to trigger challenge, then check again
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Get CSRF first
    csrf = page.evaluate("""async () => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
        });
        return r.headers.get('x-csrf-token');
    }""")
    
    # Trigger PX
    page.evaluate("""async (csrf) => {
        await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'x-csrf-token': csrf
            },
            body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
        });
    }""", csrf)
    
    time.sleep(5)
    
    # Check again
    funcs2 = page.evaluate("""() => {
        const results = {};
        
        // Check for setupEnforcement
        results.setupEnforcement = typeof window.setupEnforcement !== 'undefined';
        results.setupEnforcement0 = typeof window.setupEnforcement0 !== 'undefined';
        
        // Check container
        const container = document.getElementById('generic-challenge-container-proofofwork');
        results.hasContainer = !!container;
        if (container) {
            results.containerHTML = container.innerHTML.substring(0, 500);
            results.containerDisplay = container.style.display;
            results.containerClass = container.className;
        }
        
        // Check Roblox challenge state
        if (window.Roblox?.Challenge?.challengeContainer) {
            results.challengeContainer = true;
        }
        
        return results;
    }""")
    print("\nAfter PX challenge:", flush=True)
    print(json.dumps(funcs2, indent=2), flush=True)
    
    # Print relevant log messages
    print("\nConsole logs (challenge related):", flush=True)
    for l in logs:
        if any(kw in l['text'].lower() for kw in ['captcha', 'challenge', 'enforcement', 'arkose', 'px', 'setupenforcement']):
            print(f"  [{l['type']}] {l['text'][:300]}", flush=True)
    
    input("Enter...")
    browser.close()
