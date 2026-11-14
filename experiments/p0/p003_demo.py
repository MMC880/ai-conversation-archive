"""Persist an inspectable SYNTHETIC P0-03 corpus and original-byte checkpoints."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
from export_validation import inspect_candidate, preserve_and_validate, resume
from p003_fixtures import rich_rows, make_export, json_member, crc_corrupt, deflate_corrupt
from storage import sandbox_path, exclusive_bytes

def main():
    base=Path(__file__).resolve().parent
    root=base/'runs'/('p003-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    plain=json.dumps(rich_rows(),ensure_ascii=False).encode()
    duplicate=rich_rows();duplicate.append(duplicate[0])
    broken_edge=rich_rows();broken_edge[0]['mapping']['u']['children'].remove('a1')
    cases=[
        ('01-graph.zip',make_export(extra={'chat.html':b'<p>SYNTHETIC auxiliary; not an attachment</p>'}),'zip','parsed'),
        ('02-numbered.zip',make_export(split=True),'zip','parsed'),
        ('03-direct.json',plain,'json','parsed'),
        ('04-bad-json.zip',json_member(b'[{'),'zip','failed'),
        ('05-bad-crc.zip',crc_corrupt(),'zip','failed'),
        ('06-bad-deflate.zip',deflate_corrupt(),'zip','failed'),
        ('07-duplicate-id.zip',make_export(duplicate),'zip','failed'),
        ('08-unsafe-path.zip',make_export(extra={'../escape.txt':b'not extracted'}),'zip','failed'),
        ('09-duplicate-key.zip',json_member(plain.replace(b'"value": 42',b'"value": 42, "value": 43')),'zip','failed'),
        ('10-bad-number.zip',json_member(plain.replace(b'1700000001.125',b'1e999')),'zip','failed'),
        ('11-reverse-edge.zip',make_export(broken_edge),'zip','failed'),
        ('12-precision.zip',json_member(plain.replace(b'"value": 42',b'"value": 9007199254740993.0')),'zip','failed'),
    ]
    results=[]
    for name,data,kind,status in cases:
        path=sandbox_path(root,'inputs/'+name);exclusive_bytes(path,data)
        r=preserve_and_validate(data,root/'store',kind)
        assert r['status']==status
        assert Path(r['source_path']).read_bytes()==data
        assert hashlib.sha256(path.read_bytes()).hexdigest()==r['input_sha256']
        if status=='failed':assert resume(root/'store',r['input_sha256'],kind)['status']=='failed'
        results.append({'sample':name,'kind':kind,'bytes':len(data),'expected_status':status,'receipt':r})
    replay=preserve_and_validate(cases[0][1],root/'store')
    assert replay['duplicate_source'] and replay['status']=='parsed'
    graph=inspect_candidate(cases[0][1])
    coverage={'synthetic_only':True,'real_export_compatibility':'WAITING_REAL_SAMPLE',
        'conversations':len(graph['conversations']),'nodes':[len(r['mapping']) for r in graph['conversations']],
        'messages':graph['message_counts'],'active_paths':graph['active_paths'],'branch_points':graph['branch_points'],
        'roles':graph['role_counts'],'attachments':graph['referenced_attachments'],'warnings':graph['warnings'],
        'unknown_blocks_preserved':True,'timestamps_not_invented':True,'network_fetch_performed':False}
    outcome={'root':str(root),'samples':results,'replay':replay,'coverage':coverage,
        'parsed':sum(r['receipt']['status']=='parsed' for r in results),
        'failed':sum(r['receipt']['status']=='failed' for r in results),
        'source_objects':len(list((root/'store/sources').iterdir())),
        'success_reports':len(list((root/'store/reports').iterdir())),
        'product_compatibility_accepted':False}
    assert (outcome['parsed'],outcome['failed'],outcome['source_objects'],outcome['success_reports'])==(3,9,12,3)
    exclusive_bytes(sandbox_path(root,'RESULT.json'),(json.dumps(outcome,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps({'root':str(root),'parsed':3,'failed':9,'raw_retained':12,'duplicate_replay':True,
        'coverage':coverage},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
