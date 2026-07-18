"""Extract POW algorithm from Challenge.js."""
import re

with open('challenge_js_content.txt', 'r', encoding='utf-8') as f:
    js = f.read()

# Find proofOfWork handler ec function
# Look at position 116354 (proofOfWork registration)  
context = js[116300:117500]
print('=== proofOfWork handler registration ===')
print(context[:1200])
print('\n' + '='*60 + '\n')

# Find solution submission  
idx = js.find('challengeId:t,solution:n')
if idx >= 0:
    print('=== Solution submission ===')
    print(js[idx-200:idx+300])
    print('\n' + '='*60 + '\n')

# Find the actual proofOfWork handler function definition
# ec is at position ~292716
pos = 292700
# Find the function body
end = js.find('i_(this,"', pos + 100)
if end < 0:
    end = pos + 5000
section = js[max(0,pos-200):min(end+2000, len(js))]
print("=== proofOfWork handler 'ec' ===")
print(section[:2000])
print('\n' + '='*60 + '\n')

# Find fallback solver
idx = js.find('fallback solver')
if idx >= 0:
    print('=== Fallback solver ===')
    print(js[max(0,idx-300):idx+500])
    print('\n' + '='*60 + '\n')

# Find the COMPUTING section
idx = js.find('COMPUTING_DONE')
if idx >= 0:
    print('=== COMPUTING section ===')
    print(js[max(0,idx-500):idx+300])
    print('\n' + '='*60 + '\n')

# Find Worker usage
idx = js.find('Worker')
last_idx = js.rfind('Worker')
if idx >= 0:
    # Find worker around the solver
    for search_idx in [idx, js.find('Worker', idx+1)]:
        if search_idx >= 0 and abs(search_idx - 283744) < 5000:
            print('=== Worker near solver ===')
            print(js[max(0,search_idx-200):search_idx+500])
            print()
