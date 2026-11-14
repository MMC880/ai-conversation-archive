from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from fixtures import payload
from storage import Journal

BASE = Path(__file__).resolve().parent
(BASE / 'runs').mkdir(exist_ok=True)

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=BASE / 'runs')
        self.root = Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()

    def test_durable_receipt_and_exact_raw_recovery(self):
        journal = Journal(self.root)
        receipt = journal.accept(payload())
        self.assertIsInstance(receipt, dict, 'Acceptance requires a committed receipt')
        self.assertTrue(receipt['durable'])
        restored = Journal(self.root)
        self.assertEqual(restored.status(receipt['id']), 'pending')
        self.assertEqual(restored.recover(), 1)
        self.assertEqual((self.root / 'raw' / (receipt['id'] + '.json')).read_bytes(), payload())
        self.assertEqual(restored.status(receipt['id']), 'complete')

    def test_concurrent_dedup_and_changed_snapshot(self):
        journal = Journal(self.root)
        with ThreadPoolExecutor(max_workers=8) as pool:
            receipts = list(pool.map(journal.accept, [payload()] * 16))
        self.assertTrue(all(isinstance(r, dict) for r in receipts))
        self.assertEqual(len({r['id'] for r in receipts}), 1)
        self.assertEqual(journal.count(), 1)
        new = journal.accept(payload('新版本'))
        self.assertNotEqual(new['id'], receipts[0]['id'])
        self.assertEqual(journal.count(), 2)

    def test_process_exit_after_commit_before_projection(self):
        code = 'from pathlib import Path; from storage import Journal; from fixtures import payload; import os; Journal(Path(__import__("sys").argv[1])).accept(payload()); os._exit(73)'
        p = subprocess.run([sys.executable, '-c', code, str(self.root)], cwd=BASE)
        self.assertEqual(p.returncode, 73)
        journal = Journal(self.root)
        self.assertEqual(journal.count(), 1)
        self.assertEqual(journal.recover(), 1)
        self.assertEqual(len(list((self.root / 'raw').glob('*.json'))), 1)

    def test_projection_failure_remains_pending_and_retries(self):
        journal = Journal(self.root)
        receipt = journal.accept(payload())
        self.assertIsInstance(receipt, dict)
        (self.root / 'raw').write_text('blocked destination')
        with self.assertRaises(OSError):
            journal.recover()
        self.assertEqual(journal.status(receipt['id']), 'pending')
        (self.root / 'raw').unlink()
        self.assertEqual(journal.recover(), 1)

    def test_corrupt_existing_raw_refused_not_overwritten(self):
        journal = Journal(self.root)
        receipt = journal.accept(payload())
        self.assertIsInstance(receipt, dict)
        (self.root / 'raw').mkdir()
        target = self.root / 'raw' / (receipt['id'] + '.json')
        target.write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            journal.recover()
        self.assertEqual(target.read_bytes(), b'tampered')
        self.assertEqual(journal.status(receipt['id']), 'pending')

    def test_unknown_fields_and_secret_fields_rejected(self):
        for key in ['target_path', 'api_key', 'cookie']:
            obj = json.loads(payload()); obj[key] = 'bad'
            with self.subTest(key=key), self.assertRaises(ValueError):
                Journal(self.root).accept(json.dumps(obj).encode())

    def test_index_can_be_reconstructed_from_projected_raw(self):
        original=Journal(self.root/'original')
        a=original.accept(payload()); b=original.accept(payload('changed'))
        self.assertIsInstance(a,dict); self.assertIsInstance(b,dict)
        original.recover()
        rebuilt=Journal(self.root/'rebuilt')
        receipts=[rebuilt.accept(p.read_bytes()) for p in (self.root/'original'/'raw').glob('*.json')]
        self.assertEqual({r['id'] for r in receipts},{a['id'],b['id']})
        self.assertEqual(rebuilt.count(),2)

    def test_overflow_timestamp_rejected(self):
        raw=payload().replace(b'"timestamp": null',b'"timestamp": 1e999')
        with self.assertRaises(ValueError): Journal(self.root).accept(raw)

    def test_completed_raw_is_rechecked(self):
        journal=Journal(self.root); receipt=journal.accept(payload()); journal.recover()
        target=self.root/'raw'/(receipt['id']+'.json')
        target.write_bytes(b'corrupted after completion')
        with self.assertRaises(ValueError): journal.verify_raw()

    def test_oversized_integer_timestamp_is_validation_error(self):
        obj=json.loads(payload()); obj['messages'][0]['timestamp']=10**400
        with self.assertRaises(ValueError): Journal(self.root).accept(json.dumps(obj).encode())

if __name__ == '__main__': unittest.main(verbosity=2)
