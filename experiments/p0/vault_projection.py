"""File-level projection into a new synthetic test vault, without Obsidian APIs."""
import hashlib
import re
from storage import exclusive_bytes, sandbox_path, validate_payload

def project(root, raw, attachment):
    obj=validate_payload(raw)
    key=hashlib.sha256(raw).hexdigest()
    asset_key=hashlib.sha256(attachment).hexdigest()
    note=f'archive/{key}.md'
    asset=f'attachments/{asset_key}.png'
    note_path=sandbox_path(root,note)
    asset_path=sandbox_path(root,asset)
    blocks=[f'# P0 synthetic archive\n\nSource-SHA256: {key}\n\nCoverage: {obj["coverage"]}\n']
    for n,msg in enumerate(obj['messages'],1):
        text=msg['text']
        fence='`'*max(3,1+max((len(s) for s in re.findall(r'`+',text)),default=0))
        blocks.append(f'\n## {n}. {msg["role"]}\n\n{fence}text\n{text}\n{fence}\n')
    blocks.append(f'\n![synthetic attachment](../{asset})\n')
    exclusive_bytes(asset_path,attachment)
    exclusive_bytes(note_path,''.join(blocks).encode('utf-8'))
    return {'note':note,'attachment':asset,'source_sha256':key}
