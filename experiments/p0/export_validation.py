"""Synthetic candidate audit layered on existing P0 inspector, NOT official schema."""
import hashlib
import io
import json
import math
from pathlib import Path
import re
import zipfile
import zlib
from decimal import Decimal, DecimalException
from importer import inspect_export, safe_name
from storage import exclusive_bytes, sandbox_path

LIMIT=2_000_000  # old inspector's experiment budget; not a product limit
POLICY='p003-synthetic-candidate-v1'

class CandidateError(ValueError):
    """Stable category only, never echo an arbitrary payload or credential value."""

def _input(data,kind):
    if not isinstance(data,bytes) or not data or len(data)>LIMIT:raise CandidateError('INPUT_BUDGET_OR_TYPE')
    if kind not in ('zip','json'):raise CandidateError('UNSUPPORTED_INPUT_KIND')

def _strict_json(data):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise CandidateError('DUPLICATE_JSON_KEY')
            result[k]=v
        return result
    def constant(_):raise CandidateError('NONFINITE_JSON_NUMBER')
    def checked_float(token):
        value=float(token)
        if not math.isfinite(value):raise CandidateError('NONFINITE_JSON_NUMBER')
        # Compare decimal input and emitted JSON value, not two copies of float rounding.
        try:
            if Decimal(token)!=Decimal(str(value)):raise CandidateError('UNSUPPORTED_NUMERIC_PRECISION')
        except DecimalException as exc:raise CandidateError('UNSUPPORTED_NUMERIC_PRECISION') from exc
        return value
    def leaves(value):
        if isinstance(value,str):value.encode('utf-8')
        elif isinstance(value,float) and not math.isfinite(value):raise CandidateError('NONFINITE_JSON_NUMBER')
        elif isinstance(value,dict):
            for k,v in value.items():leaves(k);leaves(v)
        elif isinstance(value,list):
            for v in value:leaves(v)
    try:
        value=json.loads(data.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=constant,parse_float=checked_float)
        leaves(value)
        return value
    except CandidateError:raise
    except (ValueError,UnicodeError,RecursionError) as exc:raise CandidateError('INVALID_JSON_ENCODING_OR_SHAPE') from exc

def _time(obj):
    for field in ('create_time','update_time'):
        value=obj.get(field)
        if value is not None and (type(value) not in (int,float) or not 0<=value<=253402300799
            or (type(value) is float and not math.isfinite(value))):raise CandidateError('INVALID_CANDIDATE_TIME')

def inspect_candidate(data,kind='zip'):
    _input(data,kind)
    container=data
    if kind=='json':
        _strict_json(data)
        memory=io.BytesIO()
        with zipfile.ZipFile(memory,'w') as z:
            z.writestr(zipfile.ZipInfo('conversations.json',(2000,1,1,0,0,0)),data)
        container=memory.getvalue()  # deterministic internal wrapper, never a real export
    try:
        result=inspect_export(container)  # old safety, CRC, graph/cycle, unknown-field retention
    except (ValueError,TypeError,KeyError,AttributeError,RecursionError,NotImplementedError,zlib.error) as exc:
        raise CandidateError('LEGACY_INSPECTOR_REJECTED') from exc
    members={};strict_rows=[]
    with zipfile.ZipFile(io.BytesIO(container)) as z:
        for entry in z.infolist():
            if entry.is_dir():continue
            member=z.read(entry)
            members[entry.filename]={'bytes':len(member),'sha256':hashlib.sha256(member).hexdigest()}
            if re.fullmatch(r'conversations(?:-\d+)?\.json',entry.filename):
                parsed=_strict_json(member)
                if not isinstance(parsed,list):raise CandidateError('CONVERSATION_LIST_REQUIRED')
                strict_rows.extend(parsed)
    # Reuse did not coerce or discard candidate source values.
    if strict_rows!=result['conversations']:
        # Old inspector sorts chunk names; compare using the same explicit order.
        with zipfile.ZipFile(io.BytesIO(container)) as z:
            strict_rows=[]
            for name in sorted(members):
                if re.fullmatch(r'conversations(?:-\d+)?\.json',name):strict_rows.extend(_strict_json(z.read(name)))
        if strict_rows!=result['conversations']:raise CandidateError('SOURCE_PRESERVATION_MISMATCH')
    warnings=set();roles={};branches=[];referenced={}
    try:
        for row in result['conversations']:
            _time(row);nodes=row['mapping'];seen_messages=set();branch_count=0
            for key,node in nodes.items():
                parent=node.get('parent');children=node.get('children')
                if not isinstance(children,list) or any(not isinstance(c,str) for c in children) or len(children)!=len(set(children)):
                    raise CandidateError('INVALID_CHILDREN')
                if parent is not None and key not in nodes[parent].get('children',[]):raise CandidateError('MISSING_REVERSE_EDGE')
                branch_count+=len(children)>1
                msg=node.get('message')
                if msg is None:continue
                _time(msg)
                mid=msg.get('id')
                if mid is not None:
                    if not isinstance(mid,str):raise CandidateError('INVALID_MESSAGE_ID')
                    if mid in seen_messages:warnings.add('DUPLICATE_MESSAGE_ID')
                    seen_messages.add(mid)
                author=msg.get('author')
                if author is not None and not isinstance(author,dict):raise CandidateError('INVALID_AUTHOR')
                role=(author or {}).get('role')
                if role is not None and not isinstance(role,str):raise CandidateError('INVALID_ROLE')
                if role not in ('user','assistant','system','tool'):warnings.add('UNKNOWN_ROLE')
                roles[role if role is not None else 'unknown']=roles.get(role if role is not None else 'unknown',0)+1
                if 'content' not in msg or msg['content'] is None:warnings.add('MISSING_CONTENT')
                elif not isinstance(msg['content'],dict):raise CandidateError('INVALID_CONTENT')
                elif 'parts' in msg['content'] and not isinstance(msg['content']['parts'],list):raise CandidateError('INVALID_CONTENT_PARTS')
                attachments=msg.get('attachments',[])
                if not isinstance(attachments,list):raise CandidateError('INVALID_ATTACHMENTS')
                for attachment in attachments:
                    path=safe_name(attachment['path'])
                    available=kind=='zip' and path in members
                    source_ref=available and bool(re.fullmatch(r'conversations(?:-\d+)?\.json',path))
                    status='unresolved' if source_ref else ('present' if available else 'missing')
                    referenced[path]={'status':status,'bytes':members[path]['bytes'] if status=='present' else None,
                        'sha256':members[path]['sha256'] if status=='present' else None}
                    if status=='missing':warnings.add('MISSING_ATTACHMENT')
                    if source_ref:warnings.add('ATTACHMENT_POINTS_TO_CONVERSATION_SOURCE')
            branches.append(branch_count)
    except CandidateError:raise
    except (TypeError,KeyError,AttributeError) as exc:raise CandidateError('INVALID_CANDIDATE_SHAPE') from exc
    result.pop('attachments')  # old name includes all auxiliary members, not necessarily attachments
    zip_hash=result.pop('archive_sha256')
    result.update(input_kind=kind,input_sha256=hashlib.sha256(data).hexdigest(),input_bytes=len(data),
        policy=POLICY,real_export_compatibility='WAITING_REAL_SAMPLE',coverage='partial',
        members=members if kind=='zip' else {},referenced_attachments=referenced,role_counts=roles,
        branch_points=branches,warnings=sorted(warnings),
        missing_attachments=sorted(p for p,v in referenced.items() if v['status']=='missing'))
    if kind=='json':result['synthetic_wrapper_sha256']=zip_hash
    else:result['archive_sha256']=zip_hash
    return result

def preserve_and_validate(data,root,kind='zip'):
    _input(data,kind)
    key=hashlib.sha256(data).hexdigest()
    source=sandbox_path(root,f'sources/{key}.{kind}')
    duplicate=not exclusive_bytes(source,data)
    receipt={'input_sha256':key,'input_kind':kind,'source_path':str(source),'source_retained':True,'duplicate_source':duplicate}
    try:result=inspect_candidate(data,kind)
    except CandidateError as exc:
        return dict(receipt,status='failed',error_code=str(exc),real_export_compatibility='WAITING_REAL_SAMPLE')
    report=sandbox_path(root,f'reports/{key}.{kind}.{POLICY}.json')
    encoded=(json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2)+'\n').encode('utf-8')
    exclusive_bytes(report,encoded)
    return dict(receipt,status='parsed',report_path=str(report),report_sha256=hashlib.sha256(encoded).hexdigest(),
        real_export_compatibility='WAITING_REAL_SAMPLE')

def resume(root,digest,kind='zip'):
    if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):raise CandidateError('INVALID_OBJECT_ID')
    if kind not in ('zip','json'):raise CandidateError('UNSUPPORTED_INPUT_KIND')
    source=sandbox_path(root,f'sources/{digest}.{kind}')
    if source.stat().st_size>LIMIT:raise CandidateError('INPUT_BUDGET_OR_TYPE')
    data=source.read_bytes()
    if hashlib.sha256(data).hexdigest()!=digest:raise CandidateError('SOURCE_HASH_MISMATCH')
    return preserve_and_validate(data,root,kind)
