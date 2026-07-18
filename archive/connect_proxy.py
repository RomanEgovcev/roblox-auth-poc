import socket, threading, sys, select

UPSTREAM = ('127.0.0.1', 10809)
BIND = ('127.0.0.1', 18080)

def log(msg, end='\n'):
    print(f"[P] {msg}", flush=True, end=end)

def relay(src, dst, name):
    try:
        while True:
            r, _, _ = select.select([src], [], [], 30)
            if not r:
                break
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except:
        pass

def handle(client, addr):
    try:
        data = client.recv(8192)
        if not data:
            return
        first_line = data.split(b'\r\n')[0].decode('utf-8', errors='replace')
        parts = first_line.split(' ')
        method = parts[0]
        target = parts[1] if len(parts) > 1 else '?'
        log(f"{addr[1]} -> {method} {target}")

        upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        upstream.connect(UPSTREAM)
        upstream.sendall(data)

        if method == 'CONNECT':
            host_port = target  # e.g. "roblox.com:443"
            log(f"  CONNECT tunnel to {host_port}")
            # Get upstream response (should be "200 Connection established")
            resp = upstream.recv(4096)
            log(f"  Upstream resp: {resp.split(b'\\r\\n')[0].decode('utf-8', errors='replace')}")
            client.sendall(resp)

            # Now relay bidirectionally
            threads = []
            for src, dst, name in [(client, upstream, 'C-U'), (upstream, client, 'U-C')]:
                t = threading.Thread(target=relay, args=(src, dst, name), daemon=True)
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
        else:
            # Non-CONNECT (HTTP request): forward response back
            while True:
                r, _, _ = select.select([upstream], [], [], 30)
                if not r:
                    break
                data = upstream.recv(65536)
                if not data:
                    break
                client.sendall(data)
    except Exception as e:
        log(f"ERR {addr[1]}: {e}")
    finally:
        try: client.close()
        except: pass
        try: upstream.close()
        except: pass

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(BIND)
server.listen(50)
log(f"Listening on {BIND[0]}:{BIND[1]} -> {UPSTREAM[0]}:{UPSTREAM[1]}")

while True:
    client, addr = server.accept()
    threading.Thread(target=handle, args=(client, addr), daemon=True).start()
