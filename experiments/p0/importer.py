"""Bounded synthetic-export inspector. No claims about real export compatibility."""
import hashlib
import io
import json
import re
import stat
import unicodedata
import zipfile

def safe_name(name):
    if not isinstance(name, str) or not name or name.startswith('/') or '\\' in name or ':' in name:
        raise ValueError('Unsafe relative path')
    parts = name.split('/')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{prefix}{i}' for prefix in ('COM', 'LPT') for i in range(1, 10)}
    if any(p in ('', '.', '..') or p.casefold() == '.obsidian' or p[-1:] in (' ', '.') or
           any(ord(c) < 32 or c in '<>"|?*' for c in p) or p.split('.')[0].upper() in reserved for p in parts):
        raise ValueError('Unsafe path component')
    return name

def inspect_export(data):
    if len(data) > 2_000_000:
        raise ValueError('Archive budget exceeded')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            entries = z.infolist()
            if len(entries) > 50 or sum(i.file_size for i in entries) > 2_000_000:
                raise ValueError('Expanded budget exceeded')
            files, seen = {}, set()
            for entry in entries:
                name = safe_name(entry.filename.rstrip('/') if entry.is_dir() else entry.filename)
                key = unicodedata.normalize('NFC', name).casefold()
                if key in seen or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1:
                    raise ValueError('Duplicate, linked or encrypted member')
                seen.add(key)
                if not entry.is_dir():
                    files[name] = z.read(entry)
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise ValueError('Unreadable archive') from exc
    sources = sorted(n for n in files if re.fullmatch(r'conversations(?:-\d+)?\.json', n))
    if not sources:
        raise ValueError('Synthetic conversation source missing')
    rows = []
    for source in sources:
        try:
            parsed = json.loads(files[source].decode('utf-8-sig'))
        except (ValueError, UnicodeError) as exc:
            raise ValueError('Invalid JSON') from exc
        if not isinstance(parsed, list):
            raise ValueError('Conversation list required')
        rows.extend(parsed)
    paths, counts, missing, ids = [], [], set(), set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or row['id'] in ids:
            raise ValueError('Missing or duplicate conversation identity')
        ids.add(row['id'])
        nodes = row.get('mapping')
        if not isinstance(nodes, dict) or not nodes or len(nodes) > 5000:
            raise ValueError('Invalid graph')
        for node_id, node in nodes.items():
            if not isinstance(node, dict) or (node.get('parent') is not None and node['parent'] not in nodes):
                raise ValueError('Dangling parent')
            trail, here = set(), node_id
            while here is not None:
                if here in trail:
                    raise ValueError('Parent cycle')
                trail.add(here)
                here = nodes[here].get('parent')
            for child in node.get('children', []):
                if child not in nodes or nodes[child].get('parent') != node_id:
                    raise ValueError('Inconsistent child edge')
            msg = node.get('message')
            if msg is not None and not isinstance(msg, dict):
                raise ValueError('Invalid message')
            for attachment in (msg or {}).get('attachments', []):
                target = safe_name(attachment['path'])
                if target not in files:
                    missing.add(target)
        here, active = row.get('current_node'), []
        if here not in nodes:
            raise ValueError('Active branch missing')
        while here is not None:
            if nodes[here].get('message') is not None:
                active.append(here)
            here = nodes[here].get('parent')
        paths.append(active[::-1])
        counts.append(sum(node.get('message') is not None for node in nodes.values()))
    return {'compatibility': 'SYNTHETIC_ONLY', 'archive_sha256': hashlib.sha256(data).hexdigest(),
        'conversations': rows, 'active_paths': paths, 'message_counts': counts, 'missing_attachments': sorted(missing),
        'attachments': {n: {'bytes': len(v), 'sha256': hashlib.sha256(v).hexdigest()} for n, v in files.items() if n not in sources}}
