"""Start Chrome and capture stderr for extension load errors."""
import os, time, subprocess, sys, tempfile

chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext_path = "C:\\Users\\regov\\Desktop\\lua\\chromium_automation"
profile = "C:\\Users\\regov\\Desktop\\lua\\pw_profile"

import shutil
if os.path.exists(profile):
    shutil.rmtree(profile)
time.sleep(0.5)

# Capture stderr
stderr_file = tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w", encoding="utf-8")
stderr_path = stderr_file.name

proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions",
     "--enable-logging"],
    stdout=subprocess.DEVNULL, stderr=stderr_file)
stderr_file.close()

time.sleep(8)

# Check for extension-related logs in stderr
with open(stderr_path, "r", encoding="utf-8", errors="replace") as f:
    logs = f.read()

# Filter for NopeCHA/extension related lines
ext_lines = [line for line in logs.split("\n") 
             if any(x in line.lower() for x in ["extensions", "nopecha", "service_worker", "manifest", "background", "4ncg2v", "dknlfm"])]

print(f"=== Extension-related stderr lines ({len(ext_lines)} of {logs.count(chr(10))} total) ===")
for line in ext_lines[-30:]:
    print(f"  {line[:300]}")

# Also check last 20 lines for any errors
last_lines = logs.strip().split("\n")[-20:]
print(f"\n=== Last 20 lines ===")
for line in last_lines:
    print(f"  {line[:300]}")

proc.kill()
os.unlink(stderr_path)
