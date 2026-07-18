import re, json, os

# Read the SW file
with open('chromium_automation/assets/4ncg2v.js', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Search for the nopecha API URL to understand the code structure
for m in re.finditer(r'[a-zA-Z0-9_]{2,30}\s*[:=]\s*["\']([^"\']{10,200})["\']', content):
    val = m.group(1)
    if 'nopecha' in val.lower() or 'api' in val.lower()[:10]:
        print(f"URL: {m.group()[:200]}")

# Search for "key" patterns
for m in re.finditer(r'["\']([a-zA-Z0-9_\-]{20,100})["\']', content):
    val = m.group(1)
    if any(x in val.lower() for x in ['key', 'token', 'auth']):
        print(f"KEY_CANDIDATE: {val}")

# Look at the manifest key
with open('chromium_automation/manifest.json', 'r') as f:
    manifest = json.load(f)
print(f"\nManifest key field present: {'key' in manifest}")
print(f"Manifest key (first 100): {manifest.get('key', '')[:100]}")

# The free tier doesn't use a user-specific key
# Let's check the content script files too
for root, dirs, files in os.walk('chromium_automation'):
    for fname in files:
        if fname.endswith('.js'):
            path = os.path.join(root, fname)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                data = f.read()
            # Look for the actual API URL pattern
            if 'nopecha' in data.lower():
                print(f"\nContains 'nopecha': {path}")
                # Extract the URL construction
                parts = data.split('nopecha')
                for i, part in enumerate(parts[:5]):
                    ctx = part[-100:] if i > 0 else part[:100]
                    print(f"  Context {i}: ...{ctx[:150]}...")
