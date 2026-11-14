"""P0 receipt journal. SQLite is a durable spool, not the proposed product's only L0."""
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import uuid
from contextlib import contextmanager
from importer import safe_name

BASE = Path(__file__).resolve().parent
MAX_BODY = 65536

def sandbox_path(root, relative):
    root = Path(root).absolute()
    boundary = BASE / 'runs'
    if not root.is_relative_to(boundary) or not root.resolve().is_relative_to(boundary.resolve()):
        raise ValueError('Experiment path must be under p0/runs')
    target = root / safe_name(relative)
    here = target
    while True:
        if here.is_symlink() or here.is_junction():
            raise ValueError('Linked paths are forbidden in the experiment')
        if here == boundary:
            break
        here = here.parent
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path escape')
    return target

def validate_payload(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BODY:
        raise ValueError('Payload byte budget')
    def pairs(items):
        obj = {}
        for k, v in items:
            if k in obj: raise ValueError('Duplicate JSON key')
            obj[k] = v
        return obj
    def invalid_constant(value): raise ValueError('Nonfinite JSON number')
    try:
        obj = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (UnicodeError, ValueError) as exc:
        raise ValueError('Invalid JSON') from exc
    fields = {'source', 'source_conversation_id', 'coverage', 'messages'}
    if not isinstance(obj, dict) or set(obj) != fields or obj['source'] not in ('synthetic', 'codex-probe'):
        raise ValueError('Unsupported receipt envelope')
    if not isinstance(obj['source_conversation_id'], str) or not 1 <= len(obj['source_conversation_id']) <= 128:
        raise ValueError('Missing identity')
    if obj['coverage'] not in ('partial', 'unknown'):
        raise ValueError('Synthetic probe cannot claim full coverage')
    if not isinstance(obj['messages'], list) or not 1 <= len(obj['messages']) <= 100:
        raise ValueError('Message budget')
    for msg in obj['messages']:
        if (not isinstance(msg, dict) or set(msg) != {'role', 'text', 'timestamp'} or
            msg['role'] not in ('user', 'assistant', 'tool', 'system', 'unknown') or
            not isinstance(msg['text'], str) or
            (msg['timestamp'] is not None and (type(msg['timestamp']) not in (int, float) or
                not 0 <= msg['timestamp'] <= 253402300799 or
                (type(msg['timestamp']) is float and not math.isfinite(msg['timestamp']))))):
            raise ValueError('Invalid message')
    return obj

def exclusive_bytes(target, data):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != data:
            raise ValueError('Immutable file conflict')
        return False
    temp = target.parent / ('.pending-' + uuid.uuid4().hex)
    try:
        with temp.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        try:
            if os.name == 'nt':
                os.rename(temp, target)  # Windows rename refuses an existing target
            else:
                os.link(temp, target)  # POSIX link publishes without replacement
        except FileExistsError:
            if target.read_bytes() != data: raise ValueError('Concurrent conflict')
        return True
    finally:
        temp.unlink(missing_ok=True)

class Journal:
    def __init__(self, root):
        self.root = Path(root).absolute()
        self.db = sandbox_path(self.root, 'journal.sqlite3')
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS receipts (id TEXT PRIMARY KEY, source_id TEXT NOT NULL, raw BLOB NOT NULL, state TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db, timeout=10)
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def accept(self, raw):
        obj = validate_payload(raw)
        key = hashlib.sha256(raw).hexdigest()
        with self.connect() as db:
            changed = db.execute('INSERT OR IGNORE INTO receipts VALUES (?,?,?,?)',
                (key, obj['source_conversation_id'], raw, 'pending')).rowcount
        return {'id': key, 'durable': True, 'duplicate': not bool(changed)}

    def count(self):
        with self.connect() as db:
            return db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]

    def status(self, key):
        with self.connect() as db:
            return db.execute('SELECT state FROM receipts WHERE id=?', (key,)).fetchone()[0]

    def recover(self):
        with self.connect() as db:
            pending = db.execute("SELECT id,raw FROM receipts WHERE state='pending'").fetchall()
        done = 0
        for key, raw in pending:
            if hashlib.sha256(raw).hexdigest() != key:
                raise ValueError('Journal checksum mismatch')
            target = sandbox_path(self.root, f'raw/{key}.json')
            exclusive_bytes(target, raw)
            with self.connect() as db:
                db.execute("UPDATE receipts SET state='complete' WHERE id=?", (key,))
            done += 1
        return done

    def verify_raw(self):
        with self.connect() as db:
            rows=db.execute("SELECT id,raw FROM receipts WHERE state='complete'").fetchall()
        for key,raw in rows:
            target=sandbox_path(self.root,f'raw/{key}.json')
            if not target.exists() or target.read_bytes()!=raw or hashlib.sha256(raw).hexdigest()!=key:
                raise ValueError('Completed raw integrity failure')
        return len(rows)
