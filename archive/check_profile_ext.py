"""Check profile extension structure."""
import json, os

prefs_path = "C:\\Users\\regov\\Desktop\\lua\\pw_profile\\Default\\Preferences"
with open(prefs_path, "r", encoding="utf-8") as f:
    prefs = json.load(f)

extensions = prefs.get("extensions", {})
print("Extensions keys:", list(extensions.keys())[:20])

settings = extensions.get("settings", {})
print(f"Number of extension settings: {len(settings)}")
if settings:
    for ext_id, ext_data in list(settings.items())[:10]:
        state = ext_data.get("state", "N/A")
        loc = ext_data.get("location", "N/A")
        path = ext_data.get("path", "")[:100]
        print(f"  {ext_id}: state={state}, location={loc}")
        if path:
            print(f"    path: {path}")
else:
    print("  No extension settings found")

# Check for extension directories
for sub in ["Default\\Extensions", "Default\\UnpackedExtensions"]:
    d = os.path.join("C:\\Users\\regov\\Desktop\\lua\\pw_profile", sub)
    if os.path.exists(d):
        print(f"\n{sub}:")
        for item in os.listdir(d):
            print(f"  {item}")
