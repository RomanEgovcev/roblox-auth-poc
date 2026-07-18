import json
with open('C:\\Users\\regov\\Desktop\\lua\\chromium_automation\\manifest.json') as f:
    m = json.load(f)
for i, cs in enumerate(m.get('content_scripts', [])):
    if 'ow2925' in str(cs.get('js', [])):
        print('Script', i, ':', cs['js'])
        print('  matches:', cs.get('matches', []))
        print('  exclude:', cs.get('exclude_matches', []))
