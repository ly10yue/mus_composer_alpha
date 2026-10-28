import copy,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tracks import Track,validate_tracks
from curves import Curve,EASES,eased,validate_events
from model import Document

def segment(start,end,a,b,ease='linear'):return dict(start=start,end=end,**{'from':a,'to':b},ease=ease)
def track():return Track('line1','line1',[dict(beat=0.,x=.5,alpha=0.,ease='linear')])

class TrackEventTests(unittest.TestCase):
    def test_independent_channels_and_held_gaps(self):
        t=track();t.events={'x':[segment(2,4,.2,.8)],'alpha':[segment(0,8,0,1,'sine_in_out')]}
        self.assertEqual(t.pose(0),(.5,0));self.assertAlmostEqual(t.pose(3)[0],.5)
        self.assertAlmostEqual(t.pose(4)[1],.5);self.assertEqual(t.value('x',10),.8)
        self.assertEqual(t.value('speed',3),1)
    def test_all_curve_integrals_match_numeric_area(self):
        for ease in EASES:
            c=Curve(1,[segment(2,6,.2,3.6,ease)])
            n=20000;numeric=sum(c.value(2+(i+.5)*4/n)*4/n for i in range(n))
            self.assertAlmostEqual(c.distance(2,6),numeric,places=7)
            self.assertAlmostEqual(c.distance(0,8),2+numeric+7.2,places=7)
            self.assertEqual(c.value(6),3.6)
    def test_speed_is_continuous_distance_not_absolute_time_multiplier(self):
        t=track();t.events={'speed':[segment(2,4,1,3)]}
        self.assertAlmostEqual(t.distance(0,4),6)
        self.assertAlmostEqual(t.distance(2,3),1.5)
        self.assertAlmostEqual(t.distance(2,4),4)
        for point in (3,4,5,8):
            self.assertAlmostEqual(t.distance(2,point)-t.distance(2.5,point),t.distance(2,2.5))
        self.assertAlmostEqual(t.horizon(2,4,100),4,places=6)
        self.assertEqual(t.distance(4,4),0)
    def test_stopped_speed_and_later_restart(self):
        t=track();t.events={'speed':[segment(1,3,0,0),segment(3,4,1,1)]}
        self.assertEqual(t.distance(1,3),0);self.assertAlmostEqual(t.horizon(1,.5,10),3.5,places=6)
    def test_v4_roundtrip_retime_and_legacy_channel_conversion(self):
        d=Document();t=d.lines[0];t.frames=[dict(beat=0,x=.2,alpha=1,ease='smooth'),dict(beat=4,x=.8,alpha=.3,ease='hold'),dict(beat=8,x=.4,alpha=1,ease='linear')]
        before=[t.pose(at) for at in (0,1,3,4,5,8,10)]
        t.events['x']=copy.deepcopy(t.segments('x'))
        self.assertEqual(before,[t.pose(at) for at in (0,1,3,4,5,8,10)])
        t.events['speed']=[segment(2,6,1,2,'sine_in')];d.add(4,'line1',2)
        self.assertEqual(d.project()['version'],6);self.assertEqual(d.chart()['version'],6)
        self.assertEqual(Document.from_project(d.project()).project(),d.project())
        self.assertEqual(Document.from_chart(d.chart()).chart(),d.chart())
        original=d.chart()['lines'][0]['events'];distance=t.distance(2,6);d.retime(240,False)
        self.assertEqual(d.chart()['lines'][0]['events'],original)
        self.assertAlmostEqual(d.lines[0].distance(4,12),2*distance)
    def test_invalid_overlaps_ranges_and_eases(self):
        for events in [[segment(0,0,0,1)],[segment(0,2,0,1),segment(1,3,0,1)],[segment(0,2,-.1,1)],[segment(0,2,0,float('nan'))],[segment(0,2,0,1,'bad')]]:
            with self.assertRaises(ValueError):validate_events(events,'x')
        with self.assertRaises(ValueError):validate_events([segment(0,1,1,9)],'speed')
        t=track();t.events={'unknown':[]}
        with self.assertRaises(ValueError):validate_tracks([t])

if __name__=='__main__':unittest.main()
