"""
captcha_proxy.py — Local proxy for captcha_solver.html.
Serves the HTML + modified SDK + proxies Arkose API with correct Origin.
"""
import http.server
import urllib.request
import urllib.parse
import ssl
import os
import re
import sys
import json

ARROSE_HOST = "roblox-api.arkoselabs.com"
PROXY_PORT = 8080
HERE = os.path.dirname(os.path.abspath(__file__))

# Download + patch SDK on startup
SDK_CACHE = None

def get_sdk():
    global SDK_CACHE
    if SDK_CACHE:
        return SDK_CACHE
    url = f"https://{ARROSE_HOST}/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js"
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, context=ctx).read().decode("utf-8")
    # Replace all references to the Arkose host with our proxy
    data = data.replace(ARROSE_HOST, f"localhost:{PROXY_PORT}/api")
    SDK_CACHE = data
    return data


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.serve_html()
        elif self.path == "/api.js":
            self.serve_sdk()
        elif self.path.startswith("/api/"):
            self.proxy_to_arkose(self.path[4:])  # strip "/api"
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        if self.path.startswith("/api/"):
            self.proxy_to_arkose(self.path[4:])
        else:
            self.send_error(404, "Not found")

    def serve_html(self):
        html_path = os.path.join(HERE, "hundle", "captcha_solver.html")
        if not os.path.exists(html_path):
            self.send_error(500, "captcha_solver.html not found")
            return
        html = open(html_path, "r", encoding="utf-8").read()
        # Change SDK URL to our local proxy
        html = html.replace(
            'src="https://roblox-api.arkoselabs.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js"',
            'src="/api.js"',
        )
        # Also remove data-callback (our patched SDK doesn't need it, but keep it as fallback)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def serve_sdk(self):
        try:
            js = get_sdk()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(js.encode("utf-8"))
        except Exception as e:
            self.send_error(500, f"SDK load error: {e}")

    def proxy_to_arkose(self, path):
        target = f"https://{ARROSE_HOST}/api{path}"
        # Read body if POST
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        req = urllib.request.Request(target, data=body or None, method=self.command)
        # Copy relevant headers
        for h in ("Content-Type", "Accept", "User-Agent"):
            v = self.headers.get(h)
            if v:
                req.add_header(h, v)
        # OVERRIDE Origin to match roblox.com
        req.add_header("Origin", "https://www.roblox.com")
        req.add_header("Referer", "https://www.roblox.com/")

        ctx = ssl.create_default_context()
        try:
            resp = urllib.request.urlopen(req, context=ctx, timeout=15)
            self.send_response(resp.status)
            # Forward response headers (skip chunked/transfer-encoding)
            for k, v in resp.headers.items():
                if k.lower() not in ("transfer-encoding", "content-encoding", "connection", "keep-alive"):
                    self.send_header(k, v)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()
            self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            # Forward error as-is (the SDK can handle 401 etc.)
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() not in ("transfer-encoding", "content-encoding", "connection", "keep-alive"):
                    self.send_header(k, v)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_error(502, f"Proxy error: {e}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[proxy] {args[0]} {args[1]} {args[2]}")


if __name__ == "__main__":
    # Pre-download SDK on start
    print("Downloading SDK...")
    try:
        get_sdk()
        print(f"SDK loaded ({len(SDK_CACHE)} bytes)")
    except Exception as e:
        print(f"Warning: could not download SDK: {e}")
        print("The proxy will still work but SDK will be loaded on first request.")

    server = http.server.HTTPServer(("0.0.0.0", PROXY_PORT), ProxyHandler)
    print(f"\nOpen http://localhost:{PROXY_PORT}/ in your browser")
    print("Paste blob and click 'Load' — the proxy will inject correct Origin header\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
