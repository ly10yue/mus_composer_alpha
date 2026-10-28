import sys,tempfile,unittest
from pathlib import Path
from threading import Event
from concurrent.futures import CancelledError
import numpy as np,soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audio_import import is_ogg,conversion_path,write_ogg,valid_conversion

class AudioImportTests(unittest.TestCase):
    def test_real_ogg_encoding_and_source_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'original.wav';source.write_bytes(b'original bytes')
            target=conversion_path(source,root,Event());raw=np.zeros((4800,2),dtype='<i2').tobytes()
            write_ogg(raw,target,Event());self.assertTrue(is_ogg(target));self.assertTrue(valid_conversion(target))
            self.assertEqual(source.read_bytes(),b'original bytes');self.assertAlmostEqual(sf.info(target).duration,.1)
            self.assertEqual(conversion_path(source,root,Event()),target)
            source.write_bytes(b'changed bytes');self.assertNotEqual(conversion_path(source,root,Event()),target)
    def test_cancel_has_no_output_or_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'cancel.ogg';cancel=Event();cancel.set()
            with self.assertRaises(CancelledError):write_ogg(np.zeros((4800,2),dtype='<i2').tobytes(),path,cancel)
            self.assertEqual(list(Path(directory).iterdir()),[])
    def test_extension_is_not_enough_and_empty_audio_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'renamed.ogg';path.write_bytes(b'not an Ogg')
            self.assertFalse(is_ogg(path));self.assertFalse(valid_conversion(path))
            with self.assertRaises(ValueError):write_ogg(b'',path,Event())

if __name__=='__main__':unittest.main()
