import os, sys, time, json, hashlib, base64, struct

ext_path = os.path.abspath(r'C:\Users\regov\Desktop\lua\chromium_automation')
profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')

# The extension ID from the manifest's key field
# For unpacked extensions with a key field, Chrome computes the ID from the key
# ID = first 32 chars of lowercase hex of SHA256(public_key_der)
# The key in manifest is base64-encoded SPKI public key
manifest_key_b64 = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAlWiyXSK0GK0nDwOfOJ2zUvRv99E2XU6LnR67zKE5RjM2icff7Cwmo6nR5i+4UukShIyEaDdQsbC+vyTpDeaJMn+bNphPYjQxGY6spIk3KV1h71Jj0dSUOYUwGrViKg3LnC4LKtENYOsbIxTmMw8JG4oH1hU1tY4KlnSzcqiwTaDLTP0X7MVdDK0WPOyypNlkL7v1HWMjPZa32EudqcrWub/EMpMFuSugTyIu8dHaAQhW13RkU77BiMRoZfZYxbcED48YPmZS8qi3KOrymjOTWCJeDMjwy/MLCqrwhjoG1Y5jDXHFbxNUPxEJYw9mxxPTN+asraML9tywlLuzZluHwwIDAQAB"

# Chrome extension ID = first 32 hex chars of SHA256(public_key_der)
key_der = base64.b64decode(manifest_key_b64)
ext_id = hashlib.sha256(key_der).hexdigest()[:32]
print(f"[*] Computed extension ID: {ext_id}", flush=True)

# Also the hardcoded one from test_pw_login.py
ext_id_hardcoded = "hlnvzeankg3fgvaxrefvy7ezt2xj4qs6"
print(f"[*] Hardcoded extension ID: {ext_id_hardcoded}", flush=True)

# Write the extension entry that Chrome expects in Preferences
ext_entry = {
    "extensions": {
        "settings": {
            ext_id: {
                "location": 4,  # LOCATION_UNPACKED
                "manifest_version": 3,
                "path": ext_path.replace("\\", "\\\\"),
                "state": 1,
                "was_installed_by_default": False,
            }
        }
    }
}

# Ensure the profile directory exists
os.makedirs(os.path.join(profile, "Default"), exist_ok=True)

# Modify the Preferences file (or create if not exists)
prefs_path = os.path.join(profile, "Default", "Preferences")
sec_prefs_path = os.path.join(profile, "Default", "Secure Preferences")

prefs = {}
if os.path.exists(prefs_path):
    with open(prefs_path, "r", encoding="utf-8") as f:
        prefs = json.load(f)
    print("[*] Existing Preferences loaded", flush=True)
else:
    print("[*] Creating new Preferences", flush=True)

# Merge extension settings
if "extensions" not in prefs:
    prefs["extensions"] = {}
if "settings" not in prefs["extensions"]:
    prefs["extensions"]["settings"] = {}
prefs["extensions"]["settings"][ext_id] = ext_entry["extensions"]["settings"][ext_id]

with open(prefs_path, "w", encoding="utf-8") as f:
    json.dump(prefs, f, indent=2)
print(f"[+] Extension entry written to Preferences for {ext_id}", flush=True)

print("[*] Done. Now launch c2_server.py or test script - extension should load.", flush=True)
