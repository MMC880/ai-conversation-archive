import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from p003_fixtures import rich_rows, make_export, json_member, crc_corrupt, deflate_corrupt, PNG
from export_validation import inspect_candidate, preserve_and_validate, resume

BASE=Path(__file__).resolve().parent
class ExportValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=BASE/'runs');self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_all_branches_roles_raw_text_times_and_unknown_fields(self):
        raw=make_export();r=inspect_candidate(raw)
        self.assertEqual(r['conversations'],rich_rows())
        self.assertEqual(r['message_counts'],[9,1])
        self.assertEqual(r['active_paths'][0],['sys','u','a2','u2','tool','future'])
        self.assertEqual(r['branch_points'],[2,0])
        self.assertEqual(r['role_counts'],{'system':1,'user':3,'assistant':3,'tool':2,'future-role':1})
        self.assertEqual(r['input_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(r['compatibility'],'SYNTHETIC_ONLY')
        self.assertIn('UNKNOWN_ROLE',r['warnings'])
        self.assertEqual(r['referenced_attachments']['files/pic.png']['sha256'],hashlib.sha256(PNG).hexdigest())
        self.assertEqual(r['referenced_attachments']['files/missing.pdf']['status'],'missing')
    def test_direct_json_bom_and_numbered_json(self):
        raw=b'\xef\xbb\xbf'+json.dumps(rich_rows(),ensure_ascii=False).encode()
        r=inspect_candidate(raw,kind='json')
        self.assertEqual(r['input_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(r['conversations'],rich_rows())
        self.assertEqual(r['referenced_attachments']['files/pic.png']['status'],'missing')
        self.assertEqual(inspect_candidate(make_export(split=True))['message_counts'],[9,1])
    def test_duplicate_keys_are_rejected_instead_of_silently_lost(self):
        raw=json_member(b'[{"id":"first","id":"second","mapping":{}}]')
        with self.assertRaises(ValueError):inspect_candidate(raw)
        obj=json.dumps(rich_rows()).replace('"value": 42','"value": 42, "value": 43')
        with self.assertRaises(ValueError):inspect_candidate(json_member(obj.encode()))
    def test_nonfinite_invalid_timestamp_and_wrong_known_field_types(self):
        for value in [True,'yesterday',-1,10**400,float('inf'),float('nan')]:
            rows=rich_rows();rows[0]['mapping']['tool']['message']['create_time']=value
            with self.subTest(value_type=type(value).__name__),self.assertRaises(ValueError):inspect_candidate(make_export(rows))
        rows=rich_rows();rows[0]['mapping']['u']['message']['author']=[]
        with self.assertRaises(ValueError):inspect_candidate(make_export(rows))
    def test_reverse_edge_and_bad_graph_types_are_rejected_cleanly(self):
        for mutation in ['reverse','bad-parent','bad-children','missing-current']:
            rows=rich_rows();m=rows[0]['mapping']
            if mutation=='reverse':m['u']['children'].remove('a1')
            elif mutation=='bad-parent':m['u']['parent']=[]
            elif mutation=='bad-children':m['u']['children']=3
            else:rows[0]['current_node']='missing'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):inspect_candidate(make_export(rows))
    def test_duplicate_conversation_rejected_but_duplicate_message_id_preserved(self):
        rows=rich_rows();rows.append(copy.deepcopy(rows[0]))
        with self.assertRaises(ValueError):inspect_candidate(make_export(rows))
        rows=rich_rows();rows[0]['mapping']['a2']['message']['id']='m2-old'
        r=inspect_candidate(make_export(rows))
        self.assertEqual(r['conversations'],rows)
        self.assertIn('DUPLICATE_MESSAGE_ID',r['warnings'])
    def test_missing_content_is_transparent_not_invented(self):
        rows=rich_rows();del rows[1]['mapping']['x']['message']['content']
        r=inspect_candidate(make_export(rows));self.assertEqual(r['conversations'],rows)
        self.assertIn('MISSING_CONTENT',r['warnings'])
    def test_crc_invalid_utf8_broken_json_and_unknown_layout(self):
        for data in [crc_corrupt(),json_member(b'\xff'),json_member(b'[{'),json_member(b'{}'),json_member(b'[]','other.json')]:
            with self.subTest(bytes=len(data)),self.assertRaises(ValueError):inspect_candidate(data)
    def test_unsafe_input_is_retained_only_as_opaque_object_never_extracted(self):
        raw=make_export(extra={'../escape.txt':b'never extract'})
        r=preserve_and_validate(raw,self.root)
        self.assertEqual(r['status'],'failed');self.assertTrue(r['source_retained'])
        self.assertEqual(Path(r['source_path']).read_bytes(),raw)
        self.assertFalse((self.root/'escape.txt').exists());self.assertFalse((self.root/'reports').exists())
    def test_same_bytes_dedup_changed_bytes_append_and_manifest_hashes(self):
        raw=make_export();a=preserve_and_validate(raw,self.root);b=preserve_and_validate(raw,self.root)
        self.assertEqual(a['status'],'parsed');self.assertTrue(b['duplicate_source'])
        self.assertEqual(Path(a['source_path']).read_bytes(),raw)
        self.assertEqual(json.loads(Path(a['report_path']).read_text(encoding='utf-8'))['input_sha256'],a['input_sha256'])
        changed=rich_rows();changed[0]['title']='合成新快照'
        c=preserve_and_validate(make_export(changed),self.root)
        self.assertNotEqual(c['input_sha256'],a['input_sha256'])
        self.assertEqual(len(list((self.root/'sources').iterdir())),2)
    def test_parse_failure_retries_without_success_manifest_or_source_mutation(self):
        raw=json_member(b'not json');a=preserve_and_validate(raw,self.root)
        b=resume(self.root,a['input_sha256'])
        self.assertEqual(a['status'],'failed');self.assertEqual(b['status'],'failed')
        self.assertEqual(Path(a['source_path']).read_bytes(),raw)
        self.assertFalse((self.root/'reports').exists())
    def test_process_exit_after_source_checkpoint_is_recoverable(self):
        data=make_export();incoming=self.root/'incoming.zip';incoming.write_bytes(data)
        code='import os,sys;from pathlib import Path;import export_validation as m;m.inspect_candidate=lambda *a,**k:os._exit(74);m.preserve_and_validate(Path(sys.argv[1]).read_bytes(),Path(sys.argv[2]))'
        p=subprocess.run([sys.executable,'-c',code,str(incoming),str(self.root/'store')],cwd=BASE,capture_output=True)
        self.assertEqual(p.returncode,74)
        r=resume(self.root/'store',hashlib.sha256(data).hexdigest())
        self.assertEqual(r['status'],'parsed');self.assertTrue(r['duplicate_source'])
    def test_report_io_failure_and_corrupted_source_are_not_overwritten(self):
        from storage import exclusive_bytes
        def publish(path,data):
            if 'reports' in path.parts:raise OSError('simulated report media failure')
            return exclusive_bytes(path,data)
        raw=make_export()
        with patch('export_validation.exclusive_bytes',side_effect=publish),self.assertRaises(OSError):preserve_and_validate(raw,self.root)
        key=hashlib.sha256(raw).hexdigest();self.assertEqual(resume(self.root,key)['status'],'parsed')
        target=self.root/'sources'/(key+'.zip');target.write_bytes(b'corrupted')
        with self.assertRaises(ValueError):resume(self.root,key)
        self.assertEqual(target.read_bytes(),b'corrupted')
    def test_budget_and_resume_path_rejected(self):
        with self.assertRaises(ValueError):inspect_candidate(b'x'*2_000_001)
        for key in ['../escape','g'*64]:
            with self.assertRaises(ValueError):resume(self.root,key)
        raw=make_export(extra={'big.txt':b'x'*2_100_000})
        self.assertEqual(preserve_and_validate(raw,self.root)['status'],'failed')
    def test_unknown_asset_pointer_is_not_fetched_and_auxiliary_not_attachment(self):
        r=inspect_candidate(make_export(extra={'chat.html':b'<p>synthetic auxiliary</p>'}))
        self.assertIn('chat.html',r['members']);self.assertNotIn('chat.html',r['referenced_attachments'])
        self.assertEqual(len(r['referenced_attachments']),2)

    def test_precision_loss_is_explicitly_rejected_not_hidden_by_shared_float_oracle(self):
        for literal in ['9007199254740993.0','1e-400']:
            raw=json.dumps(rich_rows()).replace('"value": 42','"value": '+literal).encode()
            for kind,data in [('json',raw),('zip',json_member(raw))]:
                with self.subTest(literal=literal,kind=kind),self.assertRaises(ValueError):inspect_candidate(data,kind)
        rows=rich_rows();rows[0]['opaque_integer']=9007199254740993
        self.assertEqual(inspect_candidate(make_export(rows))['conversations'][0]['opaque_integer'],9007199254740993)

    def test_internal_wrapper_and_conversation_source_are_not_credited_as_attachments(self):
        rows=rich_rows();rows[0]['mapping']['u2']['message']['attachments']=[{'path':'conversations.json'}]
        direct=inspect_candidate(json.dumps(rows).encode(),kind='json')
        self.assertEqual(direct['referenced_attachments']['conversations.json']['status'],'missing')
        self.assertEqual(direct['members'],{})
        zipped=inspect_candidate(make_export(rows))
        self.assertEqual(zipped['referenced_attachments']['conversations.json']['status'],'unresolved')
        self.assertIsNone(zipped['referenced_attachments']['conversations.json']['sha256'])

    def test_invalid_deflate_is_retained_failure_and_retry_not_an_unhandled_exception(self):
        raw=deflate_corrupt()
        with self.assertRaises(ValueError):inspect_candidate(raw)
        receipt=preserve_and_validate(raw,self.root)
        self.assertEqual(receipt['status'],'failed')
        self.assertEqual(resume(self.root,receipt['input_sha256'])['status'],'failed')
        self.assertEqual(Path(receipt['source_path']).read_bytes(),raw)
        self.assertFalse((self.root/'reports').exists())

    def test_empty_wrong_attachment_types_are_not_silently_accepted(self):
        for value in [{},'',None]:
            rows=rich_rows();rows[0]['mapping']['u2']['message']['attachments']=value
            with self.subTest(type=type(value).__name__),self.assertRaises(ValueError):inspect_candidate(make_export(rows))

    def test_extreme_decimal_exponent_cannot_escape_failure_or_resume(self):
        raw=json.dumps(rich_rows()).replace('"value": 42','"value": 1e-9999999999999999999').encode()
        for kind,data in [('json',raw),('zip',json_member(raw))]:
            with self.subTest(kind=kind,stage='inspection'),self.assertRaises(ValueError):inspect_candidate(data,kind)
            with self.subTest(kind=kind,stage='retention'):
                receipt=preserve_and_validate(data,self.root/kind,kind)
                self.assertEqual(receipt['status'],'failed')
                self.assertEqual(receipt['error_code'],'UNSUPPORTED_NUMERIC_PRECISION')
                self.assertEqual(resume(self.root/kind,receipt['input_sha256'],kind)['status'],'failed')
                self.assertEqual(Path(receipt['source_path']).read_bytes(),data)
                self.assertFalse((self.root/kind/'reports').exists())

if __name__=='__main__':unittest.main(verbosity=2)
