"""Fetch and analyze enforcement.js and api.js."""
import requests, re

# Fetch api.js
r = requests.get(
    'https://arkoselabs.roblox.com/v2/4.4.2/api.js',
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
)
print(f'api.js: {len(r.text)} bytes, status={r.status_code}')
if r.status_code == 200:
    with open('api.js', 'w', encoding='utf-8') as f:
        f.write(r.text)
    
    # Search for how enforcement URL is constructed
    for kw in ['enforcement', 'createIframe', 'iframe', 'session', 'token', 'hash', '#', 'public_key']:
        count = r.text.count(kw)
        print(f'  "{kw}": {count} occurrences')

# Try different enforcement hash
hashes = ['504897d1cd342e063d4f67d90600cf04']
for h in hashes:
    r2 = requests.get(
        f'https://arkoselabs.roblox.com/v2/4.4.2/enforcement.{h}.js',
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    )
    print(f'enforcement.{h}.js: {len(r2.text)} bytes, status={r2.status_code}')
    if r2.status_code == 200 and len(r2.text) > 100:
        with open(f'enforcement_{h}.js', 'w', encoding='utf-8') as f:
            f.write(r2.text)
        for kw in ['session', 'token', 'hash', 'location.hash', 'parent', 'postMessage', 'init']:
            count = r2.text.count(kw)
            print(f'  "{kw}": {count} occurrences')
