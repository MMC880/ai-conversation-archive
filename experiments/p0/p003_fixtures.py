"""Synthetic candidate dialect only; no real chat records or official schema claims."""
import copy
import io
import json
import zipfile
from fixtures import conversations, export_bytes, PNG

def rich_rows():
    rows=copy.deepcopy(conversations());row=rows[0];m=row['mapping']
    row['update_time']=1700000100
    m['sys']={'parent':None,'children':['r'],'message':{'id':'ms','author':{'role':'system'},'create_time':None,'content':{'parts':['合成系统消息']}}}
    m['r']['parent']='sys'
    m['u2']['children']=['tool']
    m['tool']={'parent':'u2','children':['future'],'message':{'id':'mt','author':{'role':'tool'},'create_time':1700000001.125,'content':{'parts':['工具输出\r\n保留换行']}}}
    m['future']={'parent':'tool','children':[],'message':{'id':'mf','author':{'role':'future-role'},'create_time':0,'content':{'parts':[{'unknown_kind':'opaque','value':42}]},'metadata':{'future_key':['not','discarded']}}}
    m['r']['children'].append('edited-user')
    m['edited-user']={'parent':'r','children':['edited-answer'],'message':{'id':'meu','author':{'role':'user'},'content':{'parts':['用户编辑后的另一分支']}}}
    m['edited-answer']={'parent':'edited-user','children':[],'message':{'id':'mea','author':{'role':'assistant'},'content':{'content_type':'future-multimodal','parts':['图片说明',{'asset_pointer':'synthetic://files/pic.png','unverified_format':True}]}}}
    row['current_node']='future'
    return rows

def make_export(rows=None, split=False, extra=None):
    return export_bytes(rich_rows() if rows is None else rows,split=split,extra=extra)

def json_member(data, name='conversations.json', compression=zipfile.ZIP_STORED):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression) as z:z.writestr(name,data)
    return stream.getvalue()

def crc_corrupt():
    data=bytearray(json_member(b'[]'))
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        i=z.infolist()[0];offset=i.header_offset+30+len(i.filename.encode())+len(i.extra)
    data[offset]^=1
    return bytes(data)

def deflate_corrupt():
    data=bytearray(json_member(json.dumps(rich_rows()).encode(),compression=zipfile.ZIP_DEFLATED))
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        i=z.infolist()[0];offset=i.header_offset+30+len(i.filename.encode())+len(i.extra)
    data[offset]=0xff  # invalid DEFLATE block type, distinct from a STORED CRC error
    return bytes(data)
