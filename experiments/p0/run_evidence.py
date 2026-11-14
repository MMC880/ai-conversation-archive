"""Run a command and preserve exact local evidence. No shell or third-party code."""
import datetime
import json
from pathlib import Path
import re
import subprocess
import sys

BASE = Path(__file__).resolve().parent
label = sys.argv[1]
assert re.fullmatch(r'[a-z0-9_-]+', label)
args = sys.argv[2:]
if args and args[0] == '--':
    args = args[1:]
stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%dT%H%M%S%f%z')
out = BASE / 'evidence' / (stamp + '-' + label)
out.mkdir(parents=True)
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
try:
    run = subprocess.run(args, cwd=BASE, capture_output=True, timeout=300)
    code, stdout, stderr = run.returncode, run.stdout, run.stderr
except subprocess.TimeoutExpired as exc:
    code, stdout, stderr = 124, exc.stdout or b'', (exc.stderr or b'') + b'\nTIMEOUT after 300 seconds\n'
(out / 'stdout.txt').write_bytes(stdout)
(out / 'stderr.txt').write_bytes(stderr)
(out / 'command.json').write_text(json.dumps({'started_utc': started, 'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'cwd': str(BASE), 'argv': args, 'exit_code': code}, ensure_ascii=False, indent=2), encoding='utf-8')
print('EVIDENCE:', out)
print('EXIT:', code)
print(stdout.decode('utf-8', errors='replace')[-2500:])
print(stderr.decode('utf-8', errors='replace')[-3500:])
sys.exit(code)
