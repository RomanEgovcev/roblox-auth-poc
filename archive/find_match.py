with open(r'C:\Users\regov\Desktop\lua\chromium\manifest.json', 'r') as f:
    content = f.read()

idx = content.find('"*://*.arkoselabs.com/fc/*"')
if idx >= 0:
    before = content[:idx]
    after = content[idx:]
    # Show context
    start = max(0, idx-100)
    end = min(len(content), idx+300)
    print(content[start:end])
