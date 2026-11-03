# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BG: malformed and hostile HTTP sent straight to the production server (Waitress with the same settings as webapp/serve.py), on a
throw-away data folder. After every attack the server must still answer a normal request. Run from the repository root with the web venv."""
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, ".")
from waitress import create_server  # noqa: E402
from webapp.tests.test_runs import make_app  # noqa: E402

app, store, *_ = make_app(start_worker=False, HTTPS=False)
server = create_server(app, host="127.0.0.1", port=0, threads=8, max_request_body_size=26 * 1024 * 1024, connection_limit=100, ident="TeamScheduler")
port = server.effective_port
threading.Thread(target=server.run, daemon=True).start()
time.sleep(0.5)


def raw(data: bytes, wait=1.0, read=4096) -> bytes:
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        s.sendall(data)
        s.settimeout(wait)
        out = b""
        try:
            while len(out) < read:
                chunk = s.recv(4096)
                if not chunk:
                    break
                out += chunk
        except socket.timeout:
            pass
        return out
    except (BrokenPipeError, ConnectionResetError):
        return b"<reset>"
    finally:
        s.close()


def alive() -> bool:
    return raw(b"GET /login HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n").startswith(b"HTTP/1.1 200")


CASES = {
    "CL.TE smuggling": b"POST /login HTTP/1.1\r\nHost: x\r\nContent-Length: 4\r\nTransfer-Encoding: chunked\r\n\r\n1\r\nZ\r\nQ\r\n\r\n",
    "TE.CL smuggling": b"POST /login HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\nContent-Length: 6\r\n\r\n0\r\n\r\nGET /admin HTTP/1.1\r\nX: x",
    "duplicate Content-Length": b"POST /login HTTP/1.1\r\nHost: x\r\nContent-Length: 5\r\nContent-Length: 50\r\n\r\nhello",
    "negative Content-Length": b"POST /login HTTP/1.1\r\nHost: x\r\nContent-Length: -5\r\n\r\n",
    "huge header": b"GET / HTTP/1.1\r\nHost: x\r\nX-A: " + b"a" * 400000 + b"\r\n\r\n",
    "many headers": b"GET / HTTP/1.1\r\nHost: x\r\n" + b"".join(b"X-%d: v\r\n" % i for i in range(5000)) + b"\r\n",
    "bad version": b"GET / HTTP/9.9\r\nHost: x\r\n\r\n",
    "no host": b"GET / HTTP/1.1\r\n\r\n",
    "absolute URI": b"GET http://evil.test/login HTTP/1.1\r\nHost: x\r\n\r\n",
    "null byte path": b"GET /\x00 HTTP/1.1\r\nHost: x\r\n\r\n",
    "CRLF in path": b"GET /%0d%0aX-Evil:1 HTTP/1.1\r\nHost: x\r\n\r\n",
    "bare LF": b"GET / HTTP/1.1\nHost: x\n\n",
    "tab in header name": b"GET / HTTP/1.1\r\nHo\tst: x\r\n\r\n",
    "oversized body": b"POST /runs HTTP/1.1\r\nHost: x\r\nContent-Length: 999999999\r\n\r\n",
    "chunk overflow": b"POST /login HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\nFFFFFFFFFFFFFFFF\r\n",
    "garbage": bytes(range(256)) * 20 + b"\r\n\r\n",
    "TRACE": b"TRACE / HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n",
    "expect 100": b"POST /login HTTP/1.1\r\nHost: x\r\nExpect: 100-continue\r\nContent-Length: 3\r\n\r\n",
}
bad = []
for name, data in CASES.items():
    reply = raw(data)
    status = reply.split(b"\r\n", 1)[0][:40]
    leaks = [w for w in (b"Traceback", b"File \"/", b"werkzeug", b"waitress") if w in reply.lower() or w in reply]
    ok = alive()
    note = "" if ok and not leaks else "  <-- PROBLEM"
    if note:
        bad.append(name)
    print(f"{name:28} -> {status.decode('latin1'):24} server alive: {ok}  leaks: {[l.decode() for l in leaks]}{note}")
# a slow-headers attacker holds a connection but must not stop others
slow = [socket.create_connection(("127.0.0.1", port)) for _ in range(40)]
for s in slow:
    s.sendall(b"GET / HTTP/1.1\r\nHost: x\r\nX-Slow: ")
print("40 slow connections open; a normal request still answered:", alive())
for s in slow:
    s.close()
print("Server header:", [l for l in raw(b"GET /login HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n").split(b"\r\n") if l.lower().startswith(b"server")])
print("PROBLEMS:", bad)
