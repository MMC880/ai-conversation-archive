"""Bounded P0 loopback receiver. Not a production web server."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import secrets
import threading
from storage import Journal, MAX_BODY

class Hub:
    def __init__(self, root):
        self.journal = Journal(root)
        self.token = secrets.token_urlsafe(32)
        self.origin = 'chrome-extension://' + 'a' * 32  # synthetic source identity only
        self.audit = []
        outer = self
        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def setup(self):
                super().setup(); self.connection.settimeout(2)
            def log_message(self, *args): pass
            def answer(self, status, body=None, cors=False):
                data = b'' if body is None else json.dumps(body).encode()
                self.send_response(status)
                self.send_header('Content-Length',str(len(data)))
                self.send_header('Content-Type','application/json')
                self.send_header('Connection','close')
                if cors:
                    self.send_header('Access-Control-Allow-Origin',outer.origin)
                    self.send_header('Vary','Origin')
                    self.send_header('Access-Control-Allow-Methods','POST, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type')
                self.end_headers()
                if data: self.wfile.write(data)
                self.close_connection = True
                outer.audit.append({'method':self.command,'status':status})
            def boundary(self):
                expected = f'127.0.0.1:{outer.address[1]}'
                if self.headers.get_all('Host') != [expected]:
                    self.answer(403); return False
                origins=self.headers.get_all('Origin') or []
                if origins and origins != [outer.origin]:
                    self.answer(403); return False
                if self.path != '/ingest':
                    self.answer(404); return False
                return True
            def do_OPTIONS(self):
                if self.boundary(): self.answer(204,cors=True)
            def do_POST(self):
                if not self.boundary(): return
                tokens=self.headers.get_all('Authorization') or []
                if len(tokens)!=1 or not hmac.compare_digest(tokens[0],'Bearer '+outer.token):
                    self.answer(401); return
                lengths=self.headers.get_all('Content-Length') or []
                if self.headers.get('Transfer-Encoding') or len(lengths)!=1 or not lengths[0].isascii() or not lengths[0].isdigit():
                    self.answer(400); return
                length=int(lengths[0])
                if length>MAX_BODY:
                    self.answer(413); return
                if self.headers.get_all('Content-Type') != ['application/json']:
                    self.answer(415); return
                try:
                    raw=self.rfile.read(length)
                    if len(raw)!=length: raise ValueError('Incomplete body')
                    receipt=outer.journal.accept(raw)
                except (ValueError,UnicodeError):
                    self.answer(400); return
                except OSError:
                    self.answer(503); return
                self.answer(202,receipt,cors=bool(self.headers.get('Origin')))
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.address=self.server.server_address
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=3)

def start_hub(root):
    return Hub(root)
