import requests, json
r = requests.get('http://localhost:9222/json/versions', timeout=5)
r.raise_for_status()
data = r.json()
print('Browser:', str(data.get('Browser', ''))[:60])
print('WS:', data.get('webSocketDebuggerUrl', ''))
