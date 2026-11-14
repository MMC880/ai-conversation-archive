import json
import hashlib
import sqlite3

EXPECTED={'case_id':'codex-live-01','text':'SYNTHETIC_PAYLOAD_93B 中文'}

def evaluate(root,code):
    wire=root/'wire.jsonl'
    rows=[json.loads(s) for s in wire.read_text(encoding='utf-8').splitlines()] if wire.exists() else []
    calls=[r for r in rows if r.get('method')=='tools/call']
    if code!=0 or len(calls)!=1 or calls[0]['params']['arguments']!=EXPECTED:
        return False
    if 'CONTEXT_ONLY_47A' in wire.read_text(encoding='utf-8'):
        return False
    client=root/'client.jsonl'
    if not client.exists(): return False
    events=[json.loads(s) for s in client.read_text(encoding='utf-8-sig').splitlines() if s.strip()]
    done=[e['item'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='mcp_tool_call']
    if len(done)!=1 or done[0].get('server')!='p0_archive' or done[0].get('tool')!='capture_record' or done[0].get('error'):
        return False
    if any(e.get('item',{}).get('type') in ('command_execution','web_search') for e in events):
        return False
    if not any(e.get('type')=='turn.completed' for e in events): return False
    try:
        receipt=json.loads(done[0]['result']['content'][0]['text'])
        if receipt.get('durable') is not True or receipt.get('coverage')!='partial': return False
        dbpath=root/'receipts'/'journal.sqlite3'
        if not dbpath.exists(): return False
        db=sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True)
        try: row=db.execute('SELECT raw FROM receipts WHERE id=?',(receipt['id'],)).fetchone()
        finally: db.close()
        if row is None or hashlib.sha256(row[0]).hexdigest()!=receipt['id']: return False
        body=json.loads(row[0])
        if body['messages'] != [{'role':'user','text':EXPECTED['text'],'timestamp':None}]: return False
    except (KeyError,TypeError,ValueError,sqlite3.Error):
        return False
    # Detect known unrelated connector initialization attempts in addition to tool use.
    stderr=(root/'client.stderr.txt').read_text(encoding='utf-8',errors='replace')
    if 'server_name="obsidian"' in stderr or 'server_name="cua_repl"' in stderr: return False
    return True
