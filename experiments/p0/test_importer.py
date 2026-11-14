import copy
import hashlib
import io
import unittest
import zipfile
from fixtures import conversations, export_bytes, PNG
from importer import inspect_export

class ImportTests(unittest.TestCase):
    def inspect(self, raw):
        result = inspect_export(raw)
        self.assertIsInstance(result, dict, 'A graph/attachment inspection result is required')
        return result

    def test_branches_unknown_blocks_and_original_bytes_preserved(self):
        raw = export_bytes()
        before = hashlib.sha256(raw).hexdigest()
        result = self.inspect(raw)
        self.assertEqual(result['conversations'], conversations())
        self.assertEqual(result['active_paths'][0], ['u', 'a2', 'u2'])
        self.assertEqual(result['message_counts'], [4, 1])
        self.assertEqual(result['archive_sha256'], before)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), before)
        self.assertEqual(result['attachments']['files/pic.png']['sha256'], hashlib.sha256(PNG).hexdigest())
        self.assertEqual(result['missing_attachments'], ['files/missing.pdf'])
        self.assertEqual(result['compatibility'], 'SYNTHETIC_ONLY')

    def test_numbered_synthetic_chunks(self):
        self.assertEqual(len(self.inspect(export_bytes(split=True))['conversations']), 2)

    def test_reject_unsafe_zip_names(self):
        for name in ['../escape', '/absolute', 'C:/drive', 'x:stream', '.obsidian/main.js', 'files/CON.txt']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                inspect_export(export_bytes(extra={name: b'bad'}))

    def test_casefold_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            inspect_export(export_bytes(extra={'FILES/PIC.PNG': b'conflict'}))

    def test_corruption_and_budgets_rejected(self):
        for raw in [b'not a zip', export_bytes(extra={'huge.txt': b'x' * 2_100_000})]:
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                inspect_export(raw)

    def test_dangling_parent_and_cycle_rejected(self):
        for parent in ['missing', 'u2']:
            rows = conversations()
            rows[0]['mapping']['u']['parent'] = parent
            with self.subTest(parent=parent), self.assertRaises(ValueError):
                inspect_export(export_bytes(rows))

    def test_unsupported_or_invalid_json_not_marked_success(self):
        for obj in [{}, [{'id': 'bad', 'mapping': {}}]]:
            buf = io.BytesIO()
            import json
            with zipfile.ZipFile(buf, 'w') as z:
                z.writestr('conversations.json', json.dumps(obj))
            with self.assertRaises(ValueError):
                inspect_export(buf.getvalue())

if __name__ == '__main__':
    unittest.main(verbosity=2)
