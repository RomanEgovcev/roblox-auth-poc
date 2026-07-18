"""Investigate calling ProofOfWork directly."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Get CSRF + challenge
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    
    chall = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(async r => {{
            const h = {{}};
            r.headers.forEach((v,k) => {{ h[k] = v; }});
            return {{
                challId: h['rblx-challenge-id'],
                challType: h['rblx-challenge-type'],
                meta: h['rblx-challenge-metadata'] || ''
            }};
        }});
    }}""")
    
    chall_id = chall['challId']
    chall_type = chall['challType']
    meta_b64 = chall['meta']
    
    meta = json.loads(base64.b64decode(meta_b64))
    print(f"Challenge: {chall_id}", flush=True)
    print(f"Type: {chall_type}", flush=True)
    print(f"Meta: {json.dumps(meta, indent=2)}", flush=True)
    
    # Try calling ProofOfWork service directly
    session_id = meta['sessionId']
    
    result = page.evaluate(f"""async () => {{
        const powService = Roblox.AccountIntegrityChallengeService.ProofOfWork;
        console.log('ProofOfWork type:', typeof powService, powService);
        
        // Try to call it - it expects params
        // Let's look at what hp function expects
        // hp takes: containerId, sessionId, renderInline, callbacks
        
        // First, let's check what w_() would return
        // w_ probably parses sessionId from somewhere
        // Let's find w_ function
        
        // Check if we can find w_ in the global scope
        // Search for it
        const globalKeys = Object.getOwnPropertyNames(window).filter(k => k.length <= 2 && k.startsWith('w'));
        const challengeKeys = Object.keys(Roblox.AccountIntegrityChallengeService);
        
        // Let's try calling the challenge service directly
        // First we need a container
        const container = document.createElement('div');
        container.id = 'pow-challenge-container';
        document.body.appendChild(container);
        
        // The ProofOfWork handler takes (params)
        // params: containerId, sessionId, renderInline, onChallengeDisplayed, onChallengeCompleted, onChallengeInvalidated, onModalChallengeAbandoned
        
        return new Promise((resolve, reject) => {{
            try {{
                // Call ProofOfWork with our session
                const success = Roblox.AccountIntegrityChallengeService.ProofOfWork({{
                    containerId: 'pow-challenge-container',
                    sessionId: '{session_id}',
                    renderInline: true,
                    onChallengeDisplayed: (data) => {{
                        console.log('Challenge displayed:', data);
                    }},
                    onChallengeCompleted: (data) => {{
                        console.log('Challenge completed:', data);
                        resolve({{completed: true, data: JSON.stringify(data)}});
                    }},
                    onChallengeInvalidated: (data) => {{
                        console.log('Challenge invalidated:', data);
                        resolve({{invalidated: true, data: JSON.stringify(data)}});
                    }},
                    onModalChallengeAbandoned: null
                }});
                console.log('ProofOfWork returned:', success);
                if (success === false) {{
                    resolve({{error: 'ProofOfWork returned false (no valid session)'}});
                }}
            }} catch(e) {{
                console.error('Error calling ProofOfWork:', e);
                resolve({{error: e.message}});
            }}
            
            // Timeout after 60s
            setTimeout(() => resolve({{timeout: true}}), 60000);
        }});
    }}""")
    
    print(f"\nProofOfWork result:", flush=True)
    for k, v in result.items():
        print(f"  {k}: {v}", flush=True)
    
    # Also check what the login button looks like
    buttonInfo = page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button')).map(b => ({
            text: b.textContent?.trim()?.substring(0, 50),
            type: b.type,
            className: b.className?.substring(0, 100),
            id: b.id,
            dataTestId: b.getAttribute('data-testid'),
            onClick: b.getAttribute('onclick')?.substring(0, 200),
            outerHTML: b.outerHTML?.substring(0, 200),
        }));
        return btns;
    }""")
    print(f"\nAll buttons on page:", flush=True)
    for b in buttonInfo:
        print(f"  text='{b['text']}' type={b['type']} id={b['id']} testid={b['dataTestId']}", flush=True)
        if b['onClick']:
            print(f"    onClick: {b['onClick']}", flush=True)
    
    time.sleep(5)
    browser.close()
