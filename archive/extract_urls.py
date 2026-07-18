import re
with open("api.js", "r", encoding="utf-8") as f:
    content = f.read()
urls = re.findall(r"https?://[^\"')]+", content)
for u in sorted(set(urls)):
    print(u[:200])
