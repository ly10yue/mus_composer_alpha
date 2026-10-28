import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import Document, Note, Region, History, export_package, import_package, atomic_json

class ModelTests(unittest.TestCase):
    def test_triplet_snap_and_bar(self):
        d=Document(bpm=180,division=6);self.assertAlmostEqual(d.snap(.51),.5);self.assertAlmostEqual(d.seconds(d.snap(1/6)),1/18)
        self.assertEqual(d.snap(-2),0)
        d.grid_unit='bar';self.assertAlmostEqual(d.step,4/6);self.assertAlmostEqual(d.snap(.7),2/3)
        d.division=4;self.assertEqual(d.step,1)
    def test_tap_hold_duplicate(self):
        d=Document();self.assertIsNotNone(d.add(1,.18));self.assertIsNone(d.add(1,.18));d.add(2,.82,3)
        c=d.chart();self.assertEqual(c['notes'][1]['type'],'hold');self.assertEqual(c['notes'][1]['duration'],1.5)
    def test_region_overlay_preserves_before_after(self):
        d=Document();d.set_region(4,12,[[0,.5,1,1]],'lower');d.set_region(6,8,[[0,0,1,.5]],'upper')
        self.assertEqual([(r.start,r.end) for r in d.regions],[(0,4),(4,6),(6,8),(8,12),(12,d.end_beat)])
        self.assertEqual(d.region_at(8).label,'lower');self.assertEqual(d.region_at(6).label,'upper')
    def test_multiple_rectangles_and_empty(self):
        d=Document();d.set_region(0,4,[[0,0,.4,1],[.6,0,1,1]],'split');d.set_region(4,8,[],'blocked')
        self.assertEqual(len(d.region_at(1).rects),2);self.assertEqual(d.region_at(4).rects,[])
    def test_invalid_regions(self):
        d=Document()
        for rect in [[[1,0,0,1]],[[0,0,float('nan'),1]],[[0,-.2,1,1]]]:
            with self.assertRaises(ValueError):d.set_region(1,2,rect,'bad')
        with self.assertRaises(ValueError):d.set_region(4,2,[],'bad')
    def test_bpm_keep_beats(self):
        d=Document();d.add(4,.2,2);d.retime(240)
        self.assertEqual(d.notes[0].beat,4);self.assertEqual(d.chart()['notes'][0]['time'],1)
    def test_bpm_keep_seconds(self):
        d=Document();d.add(4,.2,2);d.set_region(3,8,[[0,0,1,.5]],'upper');d.retime(240,False)
        self.assertEqual(d.notes[0].beat,8);self.assertEqual(d.chart()['notes'][0]['time'],2)
        self.assertEqual(d.regions[1].start,6)
    def test_history_copies(self):
        d=Document();h=History();h.push(d);d.add(1,.2);d=h.undo(d);self.assertEqual(len(d.notes),0);d=h.redo(d);self.assertEqual(len(d.notes),1)
    def test_export_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);song=p/'歌曲.ogg';song.write_bytes(b'example audio')
            d=Document(title='测试',audio=str(song));d.add(4,.18);d.add(8,.82,2);d.set_region(4,12,[[0,.5,1,1]],'下半区')
            export_package(d,p/'test.interval');restored=import_package(p/'test.interval',p/'unpacked')
            self.assertEqual(restored.chart('x'),d.chart('x'));self.assertEqual(Path(restored.audio).read_bytes(),song.read_bytes())
            atomic_json(p/'project.ivproj',d.project());project=Document.from_project(json.loads((p/'project.ivproj').read_text(encoding='utf-8')))
            self.assertEqual(project.chart(),d.chart())
    def test_zip_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);d=Document().chart('../evil.ogg')
            with zipfile.ZipFile(p/'bad.interval','w') as z:z.writestr('chart.json',json.dumps(d));z.writestr('../evil.ogg','bad')
            with self.assertRaises(ValueError):import_package(p/'bad.interval',p/'out')
            self.assertFalse((p/'evil.ogg').exists())
    def test_validation_errors(self):
        d=Document();d.add(4,.5);d.set_region(0,10,[[0,0,.4,1]],'left');d.add(200,.2)
        errors,_=d.validate();self.assertTrue(any('横向' in x for x in errors));self.assertTrue(any('时长' in x for x in errors))
    def test_original_demo_round_trip(self):
        root=Path(__file__).resolve().parents[2];data=json.loads((root/'app/src/main/assets/demo.json').read_text(encoding='utf-8'));d=Document.from_chart(data,str(root/'app/src/main/assets/desultory-signals.ogg'))
        self.assertEqual(len(d.notes),622);self.assertEqual(d.validate()[0],[])
        for a,b in zip(data['notes'],d.chart()['notes']):self.assertAlmostEqual(a['time'],b['time'],places=6)
    def test_bad_project_numbers_and_gaps(self):
        d=Document();d.add(1,.2);data=d.project();data['document']['notes'][0]['beat']=float('nan')
        with self.assertRaises(ValueError):Document.from_project(data)
    def test_fill_grid(self):
        d=Document(division=6,grid_unit='bar');ids=d.fill(0,4,.18);self.assertEqual(len(ids),6);self.assertAlmostEqual(d.notes[-1].beat,10/3)
        with self.assertRaises(ValueError):d.fill(4,8,.82,1)
        d=Document(division=2);d.fill(0,4,.18,.5);self.assertFalse(any('重叠' in x for x in d.validate()[0]))
        data=d.project();data['document']['regions'][0]['start']=4
        with self.assertRaises(ValueError):Document.from_project(data)

if __name__=='__main__':unittest.main()
