"""Create a compact index of retained execution evidence and current source hashes."""
import hashlib
import json
from pathlib import Path
import re

BASE=Path(__file__).resolve().parent
rows=[]
for f in sorted((BASE/'evidence').glob('*/command.json')):
    meta=json.loads(f.read_text(encoding='utf-8'))
    stderr=(f.parent/'stderr.txt').read_text(encoding='utf-8',errors='replace')
    match=re.search(r'Ran (\d+) tests?',stderr)
    rows.append({'label':f.parent.name,'command':meta['argv'],'exit_code':meta['exit_code'],
                 'test_count':int(match[1]) if match else None,'has_skips':'skipped=' in stderr,'evidence':str(f.parent)})
sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(BASE.glob('*.py'))}
result={'synthetic_only':True,'runs':rows,'source_sha256':sources,
        'real_chatgpt_export_compatibility':'WAITING_REAL_SAMPLE','obsidian_client_rendering':'NOT_RUN',
        'mv3_and_real_dom':'NOT_RUN','hardware_power_loss':'NOT_RUN'}
(BASE/'evidence'/'INDEX.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('Indexed',len(rows),'command runs and',len(sources),'Python source files.')
for row in rows:
    print(row['label'],row['exit_code'],row['test_count'],'SKIP' if row['has_skips'] else '')
