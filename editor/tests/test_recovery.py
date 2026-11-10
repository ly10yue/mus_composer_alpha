import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import Document
from recovery import RecoveryWriter, write_snapshot


class RecoveryTests(unittest.TestCase):
    def test_edits_during_slow_write_and_unchanged_playback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'recovery.ivproj'
            writer = RecoveryWriter(None)
            doc = Document(title='First')
            release = threading.Event()
            def slow_write(*args):
                if not release.wait(3):
                    raise TimeoutError('UI waited for disk')
                write_snapshot(*args)
            try:
                with patch('recovery.write_snapshot', side_effect=slow_write) as write:
                    writer.save(path, doc, 'song.ivproj', None, background=True, revision=1)
                    doc.title = 'Edited during write'
                    release.set()
                    writer.flush()
                    self.assertEqual(json.loads(path.read_bytes())['document']['title'], 'First')
                    writer.save(path, doc, 'song.ivproj', None, background=True, revision=2)
                    writer.flush()
                    doc.lines[0].pose(4)
                    doc.lines[0].distance(4, 10)
                    with patch('recovery.capture', side_effect=AssertionError('unchanged chart copied')):
                        writer.save(path, doc, 'song.ivproj', None, background=True, revision=2)
                    self.assertEqual(write.call_count, 2)
                    self.assertEqual(json.loads(path.read_bytes())['document'], doc.project()['document'])
            finally:
                release.set()
                writer.close()
