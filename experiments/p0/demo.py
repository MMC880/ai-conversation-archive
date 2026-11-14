"""Create a persistent synthetic evidence bundle through the real loopback receiver."""
import datetime
import hashlib
import http.client
import json
from pathlib import Path
from fixtures import export_bytes, payload, PNG
from importer import inspect_export
from hub import start_hub
from storage import Journal
from vault_projection import project

BASE=Path(__file__).resolve().parent
root=BASE/'runs'/('demo-'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f'))
root.mkdir(parents=True)
archive=export_bytes()
(root/'SYNTHETIC_EXPORT.zip').write_bytes(archive)
inspection=inspect_export(archive)
(root/'export-inspection.json').write_text(json.dumps(inspection,ensure_ascii=False,indent=2),encoding='utf-8')
raw=payload('中文合成会话\n```python\nprint("你好")\n```')
hub=start_hub(root/'archive-data')
try:
    receipts=[]
    for _ in range(2):
        c=http.client.HTTPConnection(*hub.address,timeout=3)
        c.request('POST','/ingest',body=raw,headers={'Authorization':'Bearer '+hub.token,'Origin':hub.origin,'Content-Type':'application/json'})
        r=c.getresponse(); result=json.loads(r.read()); c.close()
        assert r.status==202
        receipts.append(result)
    audit=hub.audit
finally:
    hub.close()
journal=Journal(root/'archive-data')
assert journal.count()==1
assert journal.recover()==1
projection=project(root/'test-vault',raw,PNG)
note=(root/'test-vault'/projection['note']).read_bytes()
result={'synthetic':True,'compatibility':'SYNTHETIC_ONLY','receipts':receipts,'stored_receipts':journal.count(),
    'export_sha256':hashlib.sha256(archive).hexdigest(),'source_messages':inspection['message_counts'],
    'missing_attachments':inspection['missing_attachments'],'projection':projection,'note_sha256':hashlib.sha256(note).hexdigest(),
    'http_audit':audit,'receiver_stopped':not hub.thread.is_alive(),'obsidian_client_opened':False}
(root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'evidence_root':str(root),'stored_receipts':journal.count(),'receiver_stopped':result['receiver_stopped'],'synthetic':True},ensure_ascii=False,indent=2))
