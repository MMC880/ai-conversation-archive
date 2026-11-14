import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BASE=Path(__file__).resolve().parent

class McpTests(unittest.TestCase):
    def test_jsonrpc_roundtrip_only_explicit_arguments_reach_server(self):
        with tempfile.TemporaryDirectory(dir=BASE/'runs') as temp:
            reqs=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'synthetic-test','version':'1'}}},
                  {'jsonrpc':'2.0','method':'notifications/initialized'},
                  {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                  {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'capture_record','arguments':{'case_id':'local-test','text':'合成提交'}}},
                  {'jsonrpc':'2.0','id':4,'method':'unsupported'}]
            p=subprocess.run([sys.executable,'-X','utf8','mcp_probe.py','--root',temp],cwd=BASE,
                input='\n'.join(json.dumps(r) for r in reqs)+'\n',capture_output=True,text=True,encoding='utf-8',timeout=10)
            self.assertEqual(p.returncode,0,p.stderr)
            rows=[json.loads(s) for s in p.stdout.splitlines()]
            self.assertEqual([r['id'] for r in rows],[1,2,3,4])
            self.assertEqual(rows[1]['result']['tools'][0]['name'],'capture_record')
            receipt=json.loads(rows[2]['result']['content'][0]['text'])
            self.assertTrue(receipt['durable']); self.assertEqual(receipt['coverage'],'partial')
            self.assertEqual(rows[3]['error']['code'],-32601)
            wire=[json.loads(s) for s in (Path(temp)/'wire.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(wire,reqs)
            self.assertEqual(set(wire[3]['params']['arguments']),{'case_id','text'})

if __name__=='__main__': unittest.main(verbosity=2)
