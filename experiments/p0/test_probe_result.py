import json
from pathlib import Path
import tempfile
import unittest
from probe_result import evaluate, EXPECTED

BASE=Path(__file__).resolve().parent

class ProbeAcceptanceTests(unittest.TestCase):
    def test_request_without_durable_success_is_not_pass(self):
        with tempfile.TemporaryDirectory(dir=BASE/'runs') as temp:
            root=Path(temp)
            (root/'wire.jsonl').write_text(json.dumps({'method':'tools/call','params':{'name':'capture_record','arguments':EXPECTED}})+'\n',encoding='utf-8')
            (root/'client.jsonl').write_text(json.dumps({'type':'item.completed','item':{'type':'mcp_tool_call','server':'p0_archive','tool':'capture_record','error':'rejected'}})+'\n',encoding='utf-8')
            (root/'client.stderr.txt').write_text('',encoding='utf-8')
            self.assertFalse(evaluate(root,0),'Inbound request logging is not a committed archive receipt')

if __name__=='__main__': unittest.main(verbosity=2)
