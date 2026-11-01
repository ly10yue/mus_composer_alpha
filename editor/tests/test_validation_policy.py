import sys,tempfile,unittest,zipfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import Document,Note,export_package

class ValidationPolicyTests(unittest.TestCase):
    def document(self,path):
        path.write_bytes(b'audio fixture')
        return Document(audio=str(path),bpm=120,offset=.75)
    def test_chords_have_no_finger_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.document(Path(tmp)/'music.ogg')
            for track in d.lines:d.notes.append(Note(len(d.notes),4,track.id,0))
            errors,warnings=d.validate()
            self.assertEqual(errors,[]);self.assertEqual(warnings,[])
    def test_overlap_is_warning_and_package_exports_without_losing_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.document(Path(tmp)/'music.ogg');d.notes=[Note(888,4,'line1',4),Note(999,5,'line1',0)]
            errors,warnings=d.validate();self.assertEqual(errors,[])
            overlap=next(w for w in warnings if '重叠' in w)
            self.assertIn('00:02.750',overlap);self.assertIn('00:03.250',overlap)
            self.assertNotIn('888',overlap);self.assertNotIn('999',overlap)
            out=Path(tmp)/'overlap.interval';export_package(d,out)
            with zipfile.ZipFile(out) as z:self.assertEqual(len(json.loads(z.read('chart.json'))['notes']),2)
    def test_errors_and_hold_warnings_use_audio_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.document(Path(tmp)/'music.ogg');d.notes=[Note(987654,4,'line1',2)]
            d.lines[0].frames.append(dict(beat=8,x=.2,alpha=1,ease='linear'))
            _,warnings=d.validate();self.assertTrue(any('00:02.750' in w for w in warnings))
            d.notes[0].beat=500
            errors,_=d.validate();self.assertTrue(any('04:10.750' in e for e in errors));self.assertTrue(all('987654' not in e for e in errors))

if __name__=='__main__':unittest.main()
