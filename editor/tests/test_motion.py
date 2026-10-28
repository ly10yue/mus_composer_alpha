import copy,math,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import Document,Region
from motion import pose,polygon,touch_y,reachable,validate_motions,ASPECTS

def key(beat,x=0,y=0,angle=0,ease='linear'):return dict(beat=beat,x=x,y=y,angle=angle,ease=ease)

class MotionTests(unittest.TestCase):
    def test_interpolation_boundaries_and_multiple_turns(self):
        frames=[key(2,angle=0),key(6,x=.4,y=.2,angle=720)]
        self.assertEqual(pose(frames,0),(0,0,0));self.assertEqual(pose(frames,8),(.4,.2,720))
        self.assertEqual(pose(frames,4),(.2,.1,360))
        frames[0]['ease']='smooth';self.assertAlmostEqual(pose(frames,3)[0],.4*.15625)
        frames[0]['ease']='hold';self.assertEqual(pose(frames,5.999),(0,0,0));self.assertEqual(pose(frames,6),(.4,.2,720))
    def test_rotation_preserves_physical_rectangle_in_both_aspects(self):
        rect=[.3,.45,.7,.55]
        for aspect in ASPECTS:
            points=polygon(rect,[key(0,angle=90)],0,aspect)
            self.assertAlmostEqual(max(x for x,y in points)-min(x for x,y in points),.1/aspect)
            self.assertAlmostEqual(max(y for x,y in points)-min(y for x,y in points),.4*aspect)
            self.assertIsNone(touch_y(rect,[key(0,angle=90)],0,aspect,.3))
            self.assertAlmostEqual(touch_y(rect,[key(0,angle=90)],0,aspect,.5),.5)
    def test_translation_clipping_and_union(self):
        r=Region(0,10,'moving',[[.1,.1,.3,.3],[.7,.7,.9,.9]],[[key(0,y=1.2)],[]])
        for aspect in ASPECTS:
            self.assertFalse(reachable(r,1,.2,aspect));self.assertTrue(reachable(r,1,.8,aspect))
            self.assertIsNone(touch_y(r.rects[0],[key(0,x=-1)],1,aspect,.2))
    def test_overlay_preserves_original_motion_timing(self):
        d=Document();frames=[key(0),key(16,x=.5,angle=180)]
        d.set_region(0,16,[[.1,.1,.3,.3]],'moving',[frames]);d.set_region(4,8,[[0,0,1,1]],'override')
        self.assertEqual(d.region_at(2).motions,[frames]);self.assertEqual(d.region_at(10).motions,[frames])
        self.assertAlmostEqual(pose(d.region_at(10).motions[0],10)[0],.3125)
    def test_roundtrip_retime_versions(self):
        d=Document(bpm=120);self.assertEqual(d.chart()['version'],6);self.assertNotIn('motions',d.project()['document']['regions'][0])
        d.set_region(0,16,[[.1,.2,.9,.8]],'spin',[[key(0),key(8,x=.1,angle=360)]])
        self.assertEqual(d.chart()['version'],6);self.assertEqual(d.project()['version'],6)
        self.assertEqual(Document.from_project(d.project()).project(),d.project())
        restored=Document.from_chart(d.chart());self.assertEqual(restored.chart(),d.chart())
        d.retime(240,False);self.assertEqual(d.regions[0].motions[0][1]['beat'],16);self.assertEqual(d.chart()['sections'][0]['motions'][0][1]['time'],4)
        d.retime(120,True);self.assertEqual(d.regions[0].motions[0][1]['beat'],16)
    def test_invalid_motion_rejected(self):
        for frames in ([key(-.5)],[key(0),key(0)],[key(0,x=3)],[key(0,angle=float('nan'))],[key(0,ease='unknown')]):
            with self.assertRaises(ValueError):validate_motions([frames],1)
        with self.assertRaises(ValueError):validate_motions([[],[]],1)
        with self.assertRaises(ValueError):validate_motions([[key(i) for i in range(257)]],1)
    def test_validation_checks_transformed_reachability(self):
        with tempfile.NamedTemporaryFile() as f:
            d=Document(audio=f.name);d.add(2,.2);d.set_region(0,d.end_beat,[[.1,.1,.3,.3]],'offscreen',[[key(0,y=1)]])
            self.assertTrue(any('横向范围' in e for e in d.validate()[0]))

if __name__=='__main__':unittest.main()
