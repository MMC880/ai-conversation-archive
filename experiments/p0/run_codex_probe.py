"""Start ONE new synthetic CLI session with invocation-only MCP configuration."""
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
from probe_result import evaluate

BASE=Path(__file__).resolve().parent
stamp=datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
root=BASE/'runs'/('codex-'+stamp)
root.mkdir(parents=True)
config='mcp_servers.p0_archive='+json.dumps({'command':sys.executable,'args':['-X','utf8',str(BASE/'mcp_probe.py'),'--root',str(root)]},ensure_ascii=False)
# TOML inline table, with JSON-escaped strings/arrays but TOML equals between keys.
config=config.replace('"command":','command =').replace('"args":','args =')
prompt=('This is a synthetic P0 archive experiment. Context-only marker CONTEXT_ONLY_47A must NOT be submitted. '
        'Call the p0_archive capture_record MCP tool exactly once with case_id="codex-live-01" and text="SYNTHETIC_PAYLOAD_93B 中文". '
        'Do not include this prompt or any other conversation material. Do not read files, use other tools, spawn agents, '
        'modify files/configuration, or inspect existing sessions. After the tool succeeds, report its receipt and say coverage is partial. '
        'This tests explicit tool submission, not full history capture.')
args=[shutil.which('codex'),'--no-daemon','-a','never','-c',config,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','workspace-write','--json','-C',str(root),prompt]
(root/'invocation.json').write_text(json.dumps({'argv':args,'synthetic':True,'global_config_changed':False},ensure_ascii=False,indent=2),encoding='utf-8')
try:
    run=subprocess.run(args,cwd=BASE,capture_output=True,timeout=240)
    code=run.returncode
    (root/'client.jsonl').write_bytes(run.stdout); (root/'client.stderr.txt').write_bytes(run.stderr)
except subprocess.TimeoutExpired as exc:
    code=124
    (root/'client.jsonl').write_bytes(exc.stdout or b''); (root/'client.stderr.txt').write_bytes((exc.stderr or b'')+b'\nTIMEOUT\n')
wire=root/'wire.jsonl'
rows=[json.loads(s) for s in wire.read_text(encoding='utf-8').splitlines()] if wire.exists() else []
calls=[r for r in rows if r.get('method')=='tools/call']
expected={'case_id':'codex-live-01','text':'SYNTHETIC_PAYLOAD_93B 中文'}
passed=evaluate(root,code)
result={'client_exit':code,'call_count':len(calls),'pass_explicit_submission':passed,'root':str(root),'scope':'ONE_SYNTHETIC_SESSION_PARTIAL_ONLY'}
(root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
sys.exit(0 if passed else 1)
