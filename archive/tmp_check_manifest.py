import json
with open('C:\\Users\\regov\\Desktop\\lua\\chromium_automation\\manifest.json') as f:
    m = json.load(f)
cs = m.get('content_scripts', [])
for i, c in enumerate(cs):
    print(f'Script {i}:', c['js'])
    for match in c.get('matches', []):
        print(f'  match: {match}')
