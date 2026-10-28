import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import Document
from region_events import RegionChannels,validate_channel
from motion import polygon,touch_y
from agent_tools import EditSession,fingerprint

def event(start=2,end=6,a=.2,b=.8,ease='linear'):return dict(start=start,end=end,**{'from':a,'to':b},ease=ease)

class RegionEventTests(unittest.TestCase):
    def test_geometry_roundtrip_retime_and_split(self):
        d=Document();r=d.regions[0];r.events=[dict(center=[event(a=[.3,.8],b=[.7,.2],ease='sine_in_out')],angle=[event(a=0,b=180)],width=[event(a=.2,b=.8)],height=[event(a=.4,b=.2)])]
        c=RegionChannels(r.rects[0],[],r.events[0]);self.assertEqual(c.value('center',0),[.5,.5]);self.assertAlmostEqual(c.value('angle',4),90)
        points=polygon(r.rects[0],[],4,1,r.events[0]);self.assertAlmostEqual(max(p[0] for p in points)-min(p[0] for p in points),.3)
        self.assertAlmostEqual(touch_y(r.rects[0],[],4,1,.5,r.events[0]),.5)
        self.assertIsNone(touch_y(r.rects[0],[],4,1,.9,r.events[0]))
        for a in (1.1733333,1.6177777):
            for beat in (0,2,3,4,6,7):
                original=polygon(r.rects[0],[],beat,a,r.events[0]);loaded=Document.from_chart(d.chart()).regions[0]
                self.assertEqual(original,polygon(loaded.rects[0],[],beat,a,loaded.events[0]))
        self.assertEqual(d.chart()['version'],6);self.assertEqual(Document.from_project(d.project()).project(),d.project())
        d.set_region(8,12,[[0,0,1,1]],'other');self.assertEqual(d.regions[0].events,d.regions[2].events)
        before=d.regions[0].events[0]['center'][0]['start'];d.retime(240,False);self.assertEqual(d.regions[0].events[0]['center'][0]['start'],before*2)
    def test_legacy_channel_conversion(self):
        frames=[dict(beat=2,x=.1,y=-.1,angle=45,ease='smooth'),dict(beat=8,x=.2,y=.3,angle=90,ease='linear')]
        adapter=RegionChannels([.1,.2,.5,.8],frames,{})
        baked={p:copy.deepcopy(adapter.segments(p)) for p in ('center','angle','width','height')}
        for at in (0,2,4,7,8,10):
            original=polygon(adapter.rect,frames,at,1.6)
            actual=polygon(adapter.rect,frames,at,1.6,baked)
            for a,b in zip(original,actual):
                for x,y in zip(a,b):self.assertAlmostEqual(x,y)
    def test_validation(self):
        for prop,items in [('center',[event(a=[0],b=[1,1])]),('width',[event(a=0)]),('angle',[event(b=36001)]),('height',[event(),event(3,8)]),('center',[event(a=[True,0],b=[1,1])])]:
            with self.assertRaises(ValueError):validate_channel(items,prop)
        d=Document();d.regions[0].events=[dict(width=[event()])];p=d.project();p['version']=4
        with self.assertRaises(ValueError):Document.from_project(p)
        chart=d.chart();chart['version']=4
        with self.assertRaises(ValueError):Document.from_chart(chart)
    def test_agent_channels_atomic_and_preserved(self):
        s=EditSession(Document());s.call('set_track_events',dict(line_id='line1',channel='speed',events=[event(a=1,b=2)]))
        s.call('set_track_events',dict(line_id='line1',channel='x',events=[event()]))
        self.assertEqual(s.doc.lines[0].value('speed',4),1.5);before=fingerprint(s.doc)
        with self.assertRaises(ValueError):s.call('set_track_events',dict(line_id='line1',channel='alpha',events=[event(b=2)]))
        self.assertEqual(before,fingerprint(s.doc))
        s.call('set_region_center',dict(region_index=0,rect_index=0,events=[event(a=[.2,.8],b=[.8,.2])]))
        s.call('set_region_events',dict(region_index=0,rect_index=0,channel='width',events=[event()]))
        self.assertEqual(set(s.call('get_region',dict(region_index=0,rect_index=0))['events']),{'center','width'})
        s.doc.add(4,'line1');before=fingerprint(s.doc)
        with self.assertRaises(ValueError):s.call('delete_track',dict(line_id='line1'))
        self.assertEqual(before,fingerprint(s.doc));s.call('delete_track',dict(line_id='line4'));self.assertEqual(len(s.doc.lines),3)

if __name__=='__main__':unittest.main()
