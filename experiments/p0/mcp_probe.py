"""Minimal P0 stdio probe, not a production MCP implementation or history reader."""
import argparse
import json
import os
from pathlib import Path
import sys
from storage import Journal, sandbox_path

def serve(root):
    log=sandbox_path(root,'wire.jsonl'); log.parent.mkdir(parents=True,exist_ok=True)
    journal=Journal(root/'receipts')
    for line in sys.stdin:
        try:
            req=json.loads(line)
            with log.open('a',encoding='utf-8') as f:
                f.write(json.dumps(req,ensure_ascii=False)+'\n'); f.flush(); os.fsync(f.fileno())
            if 'id' not in req: continue
            method=req.get('method')
            if method=='initialize':
                result={'protocolVersion':'2025-11-25','capabilities':{'tools':{}},'serverInfo':{'name':'p0_archive_probe','version':'0.0.1'}}
            elif method=='ping': result={}
            elif method=='tools/list':
                result={'tools':[{'name':'capture_record','description':'Append one explicitly supplied SYNTHETIC P0 test message; this tool cannot access conversation history.',
                    'inputSchema':{'type':'object','properties':{'case_id':{'type':'string'},'text':{'type':'string'}},
                                   'required':['case_id','text'],'additionalProperties':False},
                    'annotations':{'readOnlyHint':False,'destructiveHint':False,'idempotentHint':True,'openWorldHint':False}}]}
            elif method=='tools/call':
                params=req.get('params',{}); args=params.get('arguments',{})
                if params.get('name')!='capture_record' or set(args)!={'case_id','text'}:
                    raise ValueError('Invalid synthetic tool call')
                raw=json.dumps({'source':'codex-probe','source_conversation_id':args['case_id'],'coverage':'partial',
                    'messages':[{'role':'user','text':args['text'],'timestamp':None}]},ensure_ascii=False).encode()
                receipt=journal.accept(raw)
                result={'content':[{'type':'text','text':json.dumps({**receipt,'coverage':'partial','received_only':'explicit tool arguments'})}]}
            else:
                print(json.dumps({'jsonrpc':'2.0','id':req['id'],'error':{'code':-32601,'message':'Method not supported by P0 probe'}}),flush=True)
                continue
            print(json.dumps({'jsonrpc':'2.0','id':req['id'],'result':result}),flush=True)
        except Exception:
            if isinstance(locals().get('req'),dict) and 'id' in req:
                print(json.dumps({'jsonrpc':'2.0','id':req['id'],'error':{'code':-32602,'message':'Invalid P0 request'}}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,required=True)
    serve(p.parse_args().root)
