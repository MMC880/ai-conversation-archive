import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from fixtures import payload, PNG
from vault_projection import project

BASE = Path(__file__).resolve().parent

class VaultTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=BASE/'runs')
        self.root=Path(self.temp.name)/'test-vault'
    def tearDown(self): self.temp.cleanup()

    def test_markdown_code_chinese_attachment_readback(self):
        raw=payload('中文\n```python\nprint("你好")\n```\n<script>bad()</script>')
        out=project(self.root,raw,PNG)
        self.assertIsInstance(out,dict,'Markdown and attachment projection required')
        note=(self.root/out['note']).read_text(encoding='utf-8')
        self.assertIn('中文',note)
        self.assertIn('print("你好")',note)
        self.assertIn('<script>bad()</script>',note)  # literal inside a longer fence, not HTML execution
        self.assertIn(out['attachment'],note)
        self.assertEqual((self.root/out['attachment']).read_bytes(),PNG)
        self.assertIn(hashlib.sha256(raw).hexdigest(),note)
        self.assertFalse((self.root/'.obsidian').exists())

    def test_duplicate_and_modified_note_do_not_overwrite(self):
        first=project(self.root,payload(),PNG)
        self.assertIsInstance(first,dict)
        note=self.root/first['note']
        original=note.read_bytes()
        self.assertEqual(project(self.root,payload(),PNG),first)
        self.assertEqual(note.read_bytes(),original)
        note.write_text('用户修改',encoding='utf-8')
        with self.assertRaises(ValueError): project(self.root,payload(),PNG)
        self.assertEqual(note.read_text(encoding='utf-8'),'用户修改')

    def test_changed_snapshot_gets_new_path(self):
        a=project(self.root,payload(),PNG); b=project(self.root,payload('更新'),PNG)
        self.assertIsInstance(a,dict); self.assertIsInstance(b,dict)
        self.assertNotEqual(a['note'],b['note'])

    def test_junction_escape_refused(self):
        self.root.mkdir()
        outside=Path(self.temp.name)/'outside'; outside.mkdir()
        link=self.root/'attachments'
        if os.name=='nt':
            p=subprocess.run(['cmd','/c','mklink','/J',str(link),str(outside)],capture_output=True)
            if p.returncode: self.skipTest('Junction creation unavailable: '+p.stderr.decode(errors='replace'))
        else: link.symlink_to(outside,target_is_directory=True)
        try:
            with self.assertRaises(ValueError): project(self.root,payload(),PNG)
            self.assertEqual(list(outside.iterdir()),[])
        finally:
            if os.name=='nt': os.rmdir(link)
            else: link.unlink()

    def test_literal_code_and_markdown_embeds_are_inert(self):
        text='```python\nif a < b and x & y:\n    pass\n```\n![outside](../../outside.png)\n![remote](https://example.invalid/img.png)\n<script>bad()</script>'
        out=project(self.root,payload(text),PNG)
        self.assertIsInstance(out,dict)
        note=(self.root/out['note']).read_text(encoding='utf-8')
        self.assertIn(text,note,'Literal source, including code operators, must survive projection')
        self.assertIn('````text\n'+text+'\n````',note,'Untrusted Markdown must be inside a longer literal fence')

    def test_experiment_boundary_itself_is_not_linked(self):
        base=Path(self.temp.name)/'pretend-base'; base.mkdir()
        outside=Path(self.temp.name)/'outside-boundary'; outside.mkdir()
        link=base/'runs'
        if os.name=='nt':
            p=subprocess.run(['cmd','/c','mklink','/J',str(link),str(outside)],capture_output=True)
            if p.returncode: self.skipTest('Boundary junction creation unavailable')
        else: link.symlink_to(outside,target_is_directory=True)
        try:
            from storage import sandbox_path
            with patch('storage.BASE',base), self.assertRaises(ValueError):
                sandbox_path(link/'new-vault','archive/a.md')
        finally:
            if os.name=='nt': os.rmdir(link)
            else: link.unlink()

if __name__=='__main__': unittest.main(verbosity=2)
