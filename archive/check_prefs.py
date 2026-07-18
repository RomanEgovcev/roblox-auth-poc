"""Check Preferences for installed extension settings."""
import json

prefs_path = "C:\\Users\\regov\\Desktop\\lua\\pw_profile\\Default\\Preferences"
with open(prefs_path, "r", encoding="utf-8") as f:
    prefs = json.load(f)

settings = prefs.get("extensions", {}).get("settings", {})

print(f"Total extension settings: {len(settings)}")
for ext_id, data in sorted(settings.items()):
    state = data.get("state", "?")
    location = data.get("location", "?")
    path = data.get("path", "")
    manifest = data.get("manifest", {})
    name = manifest.get("name", "?")
    print(f"\n{ext_id}:")
    print(f"  name: {name}")
    print(f"  state: {state}, location: {location}")
    if path:
        print(f"  path: {path[:150]}")
    # Show all keys
    important_keys = ["state", "location", "path", "manifest", "was_installed_by_oem", "from_bookmark", "install_time"]
    for k in important_keys:
        if k in data and k not in ("state", "location", "path", "manifest"):
            print(f"  {k}: {data[k]}")
    # Check for service worker registration
    if "background" in manifest:
        bg = manifest["background"]
        print(f"  background: {bg}")

# Also check last_chrome_version
last_ver = prefs.get("extensions", {}).get("last_chrome_version")
print(f"\nLast Chrome version: {last_ver}")

# Check if there's a NopeCHA entry
nopecha_id = "dknlfmjaanfblgfdfebhijalfmhmjjjo"
if nopecha_id in settings:
    print(f"\nNopeCHA extension FOUND in settings!")
else:
    print(f"\nNopeCHA extension NOT in settings")
    
# Check the extension install signature
print(f"\nInstall signature: {prefs.get('extensions', {}).get('install_signature', {})}")
