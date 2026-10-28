import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import Document
from versioning import decode
from tracks import Track,validate_tracks

def key(beat,x,alpha=1,ease='linear'):return dict(beat=beat,x=x,alpha=alpha,ease=ease)

class TrackTests(unittest.TestCase):
    def test_line_shape_and_notes_fall_without_horizontal_drift(self):
        t=Track('a','A',[key(0,.2),key(2,.2),key(4,.8)])
        self.assertAlmostEqual(t.x_at(4,4),.8)
        self.assertAlmostEqual(t.x_at(1,3),.5)
        self.assertAlmostEqual(t.x_at(2,3),.5)
        points=t.samples(1,1,5,.13)
        self.assertIn((2.,.2),points);self.assertIn((4.,.8),points)
        self.assertEqual(dict(t.samples(2.125,1,5,.13)),dict(points))
        d=Document();d.lines[0]=t;n=d.add(2,'a',2)
        for now in (0,1,2,3,4,5):
            for arrival in (2,3,4):self.assertAlmostEqual(d.note_x(n,now,arrival),t.pose(arrival)[0])
        self.assertAlmostEqual(d.note_x(n,arrival=2),.2);self.assertAlmostEqual(d.note_x(n,arrival=4),.8)
        tap=d.add(6,'a')
        for now in (0,1,2,3,4,5):self.assertAlmostEqual(d.note_x(tap,now,3),.8)
    def test_alpha_easing_and_endpoint(self):
        t=Track('a','A',[key(2,.2,0,'smooth'),key(6,.8,1)])
        self.assertEqual(t.pose(-1),(.2,0));self.assertEqual(t.pose(7),(.8,1))
        self.assertAlmostEqual(t.pose(3)[1],.15625)
        t.frames[0]['ease']='hold';self.assertEqual(t.pose(5.9),(.2,0));self.assertEqual(t.pose(6),(.8,1))
        p=t.samples(3,2,8,.3);self.assertIn((6.,.8),p);self.assertTrue(any(5.999<at<6 and abs(x-.2)<1e-9 for at,x in p))
    def test_no_note_coordinate_in_v3_roundtrip(self):
        d=Document();n=d.add(4,'line1',2);d.lines[0].frames=[key(0,.18),key(8,.3,.2)]
        for data in (d.chart(),d.project()['document']):
            self.assertNotIn('x',data['notes'][0]);self.assertEqual(data['notes'][0]['line'],'line1')
        self.assertEqual(Document.from_project(d.project()).project(),d.project())
        self.assertEqual(Document.from_chart(d.chart()).chart(),d.chart())
    def test_legacy_chart_and_project_migration(self):
        chart=dict(version=1,title='old',bpm=120,duration=60,notes=[dict(type='tap',time=1,x=.27),dict(type='hold',time=2,x=.27,duration=1)],sections=[dict(start=0,end=63,rects=[[0,0,1,1]])])
        d=Document.from_chart(chart);self.assertEqual(len(d.lines),1);self.assertEqual(d.notes[0].line,d.notes[1].line);self.assertAlmostEqual(d.note_x(d.notes[0]),.27)
        old=decode(d.project(),True);old.pop('coordinateScale');old['version']=1;old['document'].pop('lines')
        for n in old['document']['notes']:n.pop('line');n['x']=.27
        self.assertEqual(Document.from_project(old).chart(),d.chart())
    def test_retime_moves_keys_with_notes(self):
        d=Document();d.lines[0].frames.append(key(4,.5));d.add(4,'line1',2);d.retime(240,False)
        self.assertEqual(d.lines[0].frames[1]['beat'],8);self.assertEqual(d.chart()['lines'][0]['frames'][1]['time'],2)
    def test_reject_missing_line_and_bad_keys(self):
        d=Document();d.add(1,'line1');chart=d.chart();chart['notes'][0]['line']='missing'
        with self.assertRaises(ValueError):Document.from_chart(chart)
        for frames in ([],[key(0,.5),key(0,.6)],[key(0,float('nan'))],[key(0,.5,1.01)],[key(-1,.5)],[key(0,.5,ease='bad')]):
            with self.assertRaises(ValueError):validate_tracks([Track('a','A',frames)])
        with self.assertRaises(ValueError):validate_tracks([Track('a','A',[key(0,.5)]),Track('a','B',[key(0,.5)])])
    def test_bent_hold_follows_region_reachability(self):
        d=Document(audio=__file__);d.lines[0].frames=[key(0,.18),key(4,.8)];d.add(1,'line1',3);d.set_region(0,d.end_beat,[[0,0,.5,1]],'left')
        self.assertTrue(any('离开开放区域' in e for e in d.validate()[0]))
        d.set_region(0,d.end_beat,[[0,0,1,1]],'all');self.assertEqual(d.validate()[0],[])
    def test_hold_overlap_uses_current_intersection(self):
        d=Document(audio=__file__);d.lines[0].frames=[key(0,.18),key(4,.8)]
        d.add(1,'line1',3);n=d.add(3,'line2');x=d.note_x(d.notes[0],arrival=3)
        d.track('line2').frames=[key(0,x)]
        self.assertTrue(any('重叠' in e for e in d.validate()[0]))

if __name__=='__main__':unittest.main()
