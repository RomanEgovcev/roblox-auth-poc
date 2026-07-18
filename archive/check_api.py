import re
with open(r'C:\Users\regov\Desktop\lua\chromium_automation\assets\4ncg2v.js', 'r', encoding='utf-8') as f:
    content = f.read()
urls = re.findall(r'https?://[^"\'\\s]+', content)
for u in sorted(set(urls)):
    print(u)
