import http.client
import json
from pathlib import Path
import socket
import tempfile
import unittest
from fixtures import payload
from hub import start_hub
from storage import Journal

BASE = Path(__file__).resolve().parent

class HubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=BASE / 'runs')
        self.root = Path(self.temp.name)
        self.hub = start_hub(self.root)
    def tearDown(self):
        if self.hub is not None: self.hub.close()
        self.temp.cleanup()

    def request(self, method='POST', body=None, headers=None, path='/ingest'):
        self.assertIsNotNone(self.hub, 'A loopback receiver must start')
        c = http.client.HTTPConnection(*self.hub.address, timeout=3)
        h = {'Authorization': 'Bearer ' + self.hub.token, 'Origin': self.hub.origin, 'Content-Type': 'application/json'}
        h.update(headers or {})
        c.request(method, path, body=payload() if body is None else body, headers=h)
        r = c.getresponse(); data = r.read(); status=r.status; resp=dict(r.getheaders()); c.close()
        return status, data, resp

    def test_accept_only_after_durable_commit(self):
        status, body, _ = self.request()
        self.assertEqual(status, 202)
        receipt=json.loads(body)
        self.assertTrue(receipt['durable'])
        self.assertEqual(Journal(self.root).count(), 1)
        self.assertEqual(Journal(self.root).status(receipt['id']), 'pending')
        self.assertEqual(self.hub.address[0], '127.0.0.1')

    def test_bad_token_origin_host_and_type_never_persist(self):
        cases=[({'Authorization': 'Bearer WRONG'},401),({'Origin': 'https://evil.invalid'},403),
               ({'Host':'evil.invalid'},403),({'Content-Type':'text/plain'},415),({'Origin':'null'},403)]
        for headers, expected in cases:
            with self.subTest(headers=headers): self.assertEqual(self.request(headers=headers)[0], expected)
        self.assertEqual(Journal(self.root).count(),0)

    def test_bad_json_paths_large_and_full_claim_rejected(self):
        for raw,status in [(b'{',400),(b'x'*65537,413),
            (json.dumps({**json.loads(payload()),'target_path':'../outside'}).encode(),400),
            (json.dumps({**json.loads(payload()),'coverage':'full'}).encode(),400)]:
            with self.subTest(status=status): self.assertEqual(self.request(body=raw)[0],status)
        self.assertEqual(Journal(self.root).count(),0)

    def test_preflight_is_source_checked_and_not_receipt(self):
        status,body,headers=self.request('OPTIONS', b'')
        self.assertEqual(status,204)
        self.assertEqual(headers.get('Access-Control-Allow-Origin'),self.hub.origin)
        self.assertEqual(self.request('OPTIONS',b'',{'Origin':'https://evil.invalid'})[0],403)
        self.assertEqual(Journal(self.root).count(),0)

    def test_no_origin_requires_token_and_logs_do_not_contain_it(self):
        self.assertIsNotNone(self.hub)
        c=http.client.HTTPConnection(*self.hub.address,timeout=3)
        c.request('POST','/ingest',body=payload(),headers={'Content-Type':'application/json'})
        r=c.getresponse(); r.read(); self.assertEqual(r.status,401); c.close()
        self.request()
        self.assertNotIn(self.hub.token,json.dumps(self.hub.audit))
        self.assertNotIn('中文原文',json.dumps(self.hub.audit,ensure_ascii=False))

    def test_framing_attacks_rejected(self):
        self.assertIsNotNone(self.hub)
        host,port=self.hub.address
        for suffix in ['Content-Length: 1\r\nContent-Length: 2', 'Transfer-Encoding: chunked\r\nContent-Length: 1']:
            with socket.create_connection((host,port),timeout=3) as s:
                req=f'POST /ingest HTTP/1.1\r\nHost: {host}:{port}\r\nAuthorization: Bearer {self.hub.token}\r\n{suffix}\r\n\r\nx'
                s.sendall(req.encode()); answer=s.recv(4096)
                self.assertIn(b'400',answer.split(b'\r\n',1)[0])
        self.assertEqual(Journal(self.root).count(),0)

if __name__ == '__main__': unittest.main(verbosity=2)
