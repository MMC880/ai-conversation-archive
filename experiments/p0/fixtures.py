"""Entirely synthetic fixtures. They are NOT samples of verified ChatGPT exports."""
import copy
import io
import json
import zipfile
import struct
import zlib

def _png_chunk(kind, data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))

PNG = (bytes.fromhex('89504e470d0a1a0a') +
       _png_chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0)) +
       _png_chunk(b'IDAT',zlib.compress(b'\x00\xff\x00\x00\xff')) + _png_chunk(b'IEND',b''))

def conversations():
    return [
        {'id': 'synthetic-one', 'title': '中文：分支与代码', 'current_node': 'u2', 'create_time': None,
         'mapping': {
             'r': {'parent': None, 'children': ['u'], 'message': None},
             'u': {'parent': 'r', 'children': ['a1', 'a2'], 'message': {'id': 'm1', 'author': {'role': 'user'}, 'create_time': None,
                 'content': {'content_type': 'text', 'parts': ['保留原文\n```python\nprint("你好")\n```']}}},
             'a1': {'parent': 'u', 'children': [], 'message': {'id': 'm2-old', 'author': {'role': 'assistant'}, 'content': {'parts': ['旧回答']}}},
             'a2': {'parent': 'u', 'children': ['u2'], 'message': {'id': 'm2-new', 'author': {'role': 'assistant'}, 'content': {'parts': ['新回答', {'unknown_block': 42}]}}},
             'u2': {'parent': 'a2', 'children': [], 'message': {'id': 'm3', 'author': {'role': 'user'}, 'content': {'parts': ['附件核对']},
                 'attachments': [{'path': 'files/pic.png'}, {'path': 'files/missing.pdf'}]}},
         }, 'unknown_top_level': {'preserve': True}},
        {'id': 'synthetic-two', 'title': '第二段合成对话', 'current_node': 'x',
         'mapping': {'x': {'parent': None, 'children': [], 'message': {'id': 'm4', 'author': {'role': 'tool'},
             'content': {'parts': ['工具输出'], 'unrecognized': 'preserve'}, 'create_time': 1700000000}}}}
    ]

def export_bytes(items=None, extra=None, split=False):
    items = copy.deepcopy(conversations() if items is None else items)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        if split:
            for n, item in enumerate(items):
                z.writestr(f'conversations-{n:03}.json', json.dumps([item], ensure_ascii=False))
        else:
            z.writestr('conversations.json', json.dumps(items, ensure_ascii=False))
        z.writestr('files/pic.png', PNG)
        for name, data in (extra or {}).items():
            z.writestr(name, data)
    return buf.getvalue()

def payload(text='中文原文', source_id='synthetic-one'):
    return json.dumps({'source': 'synthetic', 'source_conversation_id': source_id, 'coverage': 'partial',
        'messages': [{'role': 'user', 'text': text, 'timestamp': None}]}, ensure_ascii=False).encode('utf-8')
