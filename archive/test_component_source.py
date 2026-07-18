"""Get the login component source and hooks to understand what blocks the API call."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=60000)
    time.sleep(8)
    
    page.fill("#login-username", USER)
    page.fill("#login-password", PASS)
    time.sleep(0.5)
    
    # Get BOTH the function component (depth 5) and class component (depth 6) sources
    info = page.evaluate("""() => {
        const btn = document.querySelector('#login-button');
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        let fiber = btn[fiberKey];
        
        // Walk up 5 levels to get the login form component (tag 0)
        let comp5 = fiber;
        for (let i = 0; i < 5 && comp5; i++) comp5 = comp5.return;
        
        // Walk up 6 levels to get the class component (tag 1)
        let comp6 = fiber;
        for (let i = 0; i < 6 && comp6; i++) comp6 = comp6.return;
        
        const result = {};
        
        if (comp5 && comp5.tag === 0) {
            result.formComponentSource = comp5.type.toString();
            result.formComponentSourceLength = comp5.type.toString().length;
        }
        
        if (comp6 && comp6.tag === 1) {
            // Class component - get its prototype for methods
            const cls = comp6.type;
            result.classComponentName = cls.name || 'anonymous';
            result.classComponentSource = cls.toString();
            
            // Check prototype methods
            const protoMethods = [];
            let proto = cls.prototype;
            while (proto && proto !== Object.prototype) {
                const names = Object.getOwnPropertyNames(proto);
                for (const name of names) {
                    if (name !== 'constructor') {
                        protoMethods.push({
                            name,
                            source: proto[name].toString().substring(0, 2000)
                        });
                    }
                }
                proto = Object.getPrototypeOf(proto);
            }
            result.classMethods = protoMethods;
            
            // Check instance state
            const instance = comp6.stateNode;
            if (instance) {
                result.instanceKeys = Object.keys(instance).filter(k => k.startsWith('_') || k === 'state' || k === 'props');
                if (instance.state) {
                    const stateStr = JSON.stringify(instance.state);
                    result.instanceState = stateStr?.substring(0, 1000);
                }
                if (instance.props) {
                    const propsStr = JSON.stringify(instance.props);
                    result.instanceProps = propsStr?.substring(0, 1000);
                }
            }
        }
        
        return result;
    }""")
    
    if 'formComponentSource' in info:
        print(f"Form component source ({info.get('formComponentSourceLength', 0)} chars):", flush=True)
        print(info['formComponentSource'], flush=True)
    
    if 'classComponentName' in info:
        print(f"\n\nClass component: {info['classComponentName']}", flush=True)
        print(f"Source: {info.get('classComponentSource', '')[:2000]}", flush=True)
        
        print(f"\nMethods:", flush=True)
        for m in info.get('classMethods', []):
            print(f"\n  {m['name']}:", flush=True)
            print(f"    {m['source']}", flush=True)
        
        if 'instanceState' in info:
            print(f"\nInstance state: {info['instanceState']}", flush=True)
        if 'instanceProps' in info:
            print(f"\nInstance props: {info['instanceProps']}", flush=True)
    
    # Also try calling onFormSubmit directly
    callResult = page.evaluate("""async () => {
        // Find the class component instance and call its onFormSubmit
        const btn = document.querySelector('#login-button');
        const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber'));
        let fiber = btn[fiberKey];
        // Walk up 6 levels to get the class component
        for (let i = 0; i < 6 && fiber; i++) fiber = fiber.return;
        
        if (fiber && fiber.tag === 1) {
            const instance = fiber.stateNode;
            // Call onFormSubmit - it might be a method or a prop
            if (typeof instance.onFormSubmit === 'function') {
                return 'onFormSubmit method found: ' + instance.onFormSubmit.toString().substring(0, 500);
            }
            // Check if it's in props
            const props = instance.props;
            if (props && typeof props.onFormSubmit === 'function') {
                // Try calling it
                try {
                    const result = props.onFormSubmit();
                    return {called: true, result: String(result), source: props.onFormSubmit.toString().substring(0, 1000)};
                } catch(e) {
                    return {called: true, error: e.message};
                }
            }
            
            // Check all props
            const propNames = props ? Object.keys(props) : [];
            return {noOnFormSubmit: true, propNames, instanceKeys: Object.keys(instance).filter(k => !k.startsWith('_'))};
        }
        
        return 'no class component found';
    }""")
    
    print(f"\n\nCall onFormSubmit:", flush=True)
    if isinstance(callResult, dict):
        for k, v in callResult.items():
            print(f"  {k}: {v}", flush=True)
    else:
        print(f"  {callResult}", flush=True)
    
    time.sleep(2)
    browser.close()
