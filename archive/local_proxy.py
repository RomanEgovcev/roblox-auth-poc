"""Forward proxy that routes nopecha.com through VPN, everything else direct.
Handles CONNECT tunneling properly."""
import socket
import select
import threading
import urllib.request
import urllib.error
import json
import sys
import ssl
import time

VPN_HTTP_PROXY = "http://127.0.0.1:10809"
LOCAL_PORT = 8888
PROXY_HOST = "127.0.0.1"

captured_requests = []

def handle_client(client_sock):
    try:
        client_sock.settimeout(30)
        data = client_sock.recv(4096)
        if not data:
            return
        request_line = data.split(b'\r\n')[0].decode('utf-8', errors='replace')
        parts = request_line.split(' ')
        method = parts[0]
        if method == 'CONNECT':
            handle_connect(client_sock, data)
        else:
            handle_http(client_sock, data)
    except Exception as e:
        print(f"[ERR] handle_client: {e}", flush=True)
    finally:
        try:
            client_sock.close()
        except:
            pass

def handle_connect(client_sock, initial_data):
    request_line = initial_data.split(b'\r\n')[0].decode('utf-8', errors='replace')
    parts = request_line.split(' ')
    host_port = parts[1]
    host, _, port_str = host_port.partition(':')
    port = int(port_str) if port_str else 443
    
    headers_end = initial_data.find(b'\r\n\r\n')
    extra_data = initial_data[headers_end + 4:] if headers_end >= 0 else b''
    
    use_vpn = 'nopecha' in host.lower()
    target = (host, port)
    
    print(f"[CONNECT] {host}:{port} {'via VPN' if use_vpn else 'direct'} (extra={len(extra_data)}b)", flush=True)
    
    try:
        if use_vpn:
            proxy_host = "127.0.0.1"
            proxy_port = 10809
            remote = socket.create_connection((proxy_host, proxy_port), timeout=15)
            remote.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode())
            proxy_resp = remote.recv(4096)
            if b"200" not in proxy_resp:
                print(f"  [VPN CONNECT] failed: {proxy_resp[:200]}", flush=True)
                client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                remote.close()
                return
            print(f"  [VPN CONNECT] tunnel established", flush=True)
        else:
            remote = socket.create_connection(target, timeout=15)
        
        client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        if extra_data:
            print(f"  [PIPELINE] forwarding {len(extra_data)}b", flush=True)
            remote.sendall(extra_data)
        relay(client_sock, remote)
    except Exception as e:
        print(f"  [CONNECT ERROR] {host}:{port} -> {e}", flush=True)
        try:
            client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        except:
            pass

def relay(sock1, sock2):
    socks = [sock1, sock2]
    try:
        while True:
            r, _, x = select.select(socks, [], socks, 5)
            if x:
                break
            if not r:
                continue
            for s in r:
                data = s.recv(65536)
                if not data:
                    return
                if s is sock1:
                    sock2.sendall(data)
                else:
                    sock1.sendall(data)
    except:
        pass
    finally:
        try: sock1.close()
        except: pass
        try: sock2.close()
        except: pass

def handle_http(client_sock, initial_data):
    request_line = initial_data.split(b'\r\n')[0].decode('utf-8', errors='replace')
    parts = request_line.split(' ')
    if len(parts) < 2:
        return
    method = parts[0]
    url = parts[1]
    use_vpn = 'nopecha' in url.lower()
    print(f"[HTTP] {method} {url[:100]} {'via VPN' if use_vpn else 'direct'}", flush=True)
    try:
        if use_vpn:
            proxy_handler = urllib.request.ProxyHandler({'http': VPN_HTTP_PROXY, 'https': VPN_HTTP_PROXY})
            opener = urllib.request.build_opener(proxy_handler)
            headers = {}
            body_start = initial_data.find(b'\r\n\r\n') + 4
            for line in initial_data.split(b'\r\n')[1:]:
                if b':' in line:
                    k, v = line.split(b':', 1)
                    k = k.decode('utf-8', errors='replace').strip()
                    v = v.decode('utf-8', errors='replace').strip()
                    if k.lower() not in ('host', 'connection', 'proxy-connection'):
                        headers[k] = v
            body = initial_data[body_start:] if body_start < len(initial_data) else None
            req = urllib.request.Request(url, data=body, method=method, headers=headers)
            resp = opener.open(req, timeout=30)
            status = resp.status
            resp_body = resp.read()
            resp_headers = dict(resp.headers)
            if 'nopecha' in url.lower() and 'funcaptcha' in url.lower():
                captured_requests.append({
                    'url': url, 'method': method,
                    'request_body': body.decode() if body else '',
                    'response_body': resp_body.decode(errors='replace')[:5000],
                    'status': status
                })
                with open('proxy_captured.json', 'w') as f:
                    json.dump(captured_requests, f, indent=2)
                print(f"[CAPTURED] {url[:80]} -> {status}", flush=True)
            resp_line = f"HTTP/1.1 {status} OK\r\n".encode()
            client_sock.sendall(resp_line)
            for k, v in resp_headers.items():
                if k.lower() not in ('transfer-encoding', 'content-encoding', 'connection', 'proxy-connection'):
                    client_sock.sendall(f"{k}: {v}\r\n".encode())
            client_sock.sendall(b"Content-Length: " + str(len(resp_body)).encode() + b"\r\n\r\n")
            client_sock.sendall(resp_body)
        else:
            direct_url = url
            req = urllib.request.Request(direct_url, method=method)
            resp = urllib.request.urlopen(req, timeout=30)
            status = resp.status
            resp_body = resp.read()
            resp_line = f"HTTP/1.1 {status} OK\r\n".encode()
            client_sock.sendall(resp_line)
            for k, v in resp.headers.items():
                if k.lower() not in ('transfer-encoding', 'content-encoding'):
                    client_sock.sendall(f"{k}: {v}\r\n".encode())
            client_sock.sendall(b"Content-Length: " + str(len(resp_body)).encode() + b"\r\n\r\n")
            client_sock.sendall(resp_body)
    except urllib.error.HTTPError as e:
        try:
            client_sock.sendall(f"HTTP/1.1 {e.code} Error\r\n\r\n".encode())
        except:
            pass
    except Exception as e:
        print(f"[HTTP ERROR] {url[:80]} -> {e}", flush=True)
        try:
            client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        except:
            pass

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((PROXY_HOST, LOCAL_PORT))
    server.listen(50)
    print(f"[*] Local proxy running on {PROXY_HOST}:{LOCAL_PORT}", flush=True)
    print(f"[*] nopecha.com -> HTTP proxy at {VPN_HTTP_PROXY} (VPN)", flush=True)
    print(f"[*] All other traffic -> direct", flush=True)
    print(f"[*] Waiting for connections...", flush=True)
    while True:
        client, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(client,), daemon=True)
        t.start()

if __name__ == '__main__':
    main()
