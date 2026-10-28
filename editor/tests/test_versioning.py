import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import Document
from motion import polygon
from versioning import APP_VERSION,decode
from agent_tools import EditSession

class VersionTests(unittest.TestCase):
    def test_011_fixture_migrates_once_without_changing_geometry(self):
        raw=json.loads((Path(__file__).parent/'fixtures/composer-0.11.0.ivproj').read_text(encoding='utf-8'));before=copy.deepcopy(raw)
        d=Document.from_project(raw);r=d.regions[0];original=[polygon(r.rects[0],[],b,1.6,r.events[0]) for b in (0,1,2,3,4,6)]
        for _ in range(10):
            export=d.project();self.assertEqual(export['appVersion'],APP_VERSION);self.assertEqual(export['coordinateScale'],100);self.assertEqual(export['version'],6)
            self.assertEqual(export['document']['regions'][0]['rects'],[[0,0,100,100]])
            self.assertEqual(export['document']['lines'][0]['frames'][0]['x'],50)
            d=Document.from_project(export)
        self.assertEqual(raw,before);r=d.regions[0];self.assertEqual(original,[polygon(r.rects[0],[],b,1.6,r.events[0]) for b in (0,1,2,3,4,6)])
    def test_spatial_scaling_excludes_alpha_speed_angle_and_time(self):
        d=Document();d.lines[0].frames=[dict(beat=0,x=.5,alpha=.7,ease='linear')];d.lines[0].events={'x':[dict(start=2,end=4,**{'from':.3,'to':.8},ease='linear')],'speed':[dict(start=2,end=4,**{'from':1,'to':2},ease='linear')]}
        d.regions[0].motions=[[dict(beat=4,x=.1,y=-.2,angle=90,ease='linear')]]
        chart=d.chart();line=chart['lines'][0];self.assertEqual(line['frames'][0]['alpha'],.7);self.assertEqual(line['events']['x'][0]['to'],80);self.assertEqual(line['events']['speed'][0]['to'],2)
        f=chart['sections'][0]['motions'][0][0];self.assertEqual((f['x'],f['y'],f['angle'],f['time']),(10,-20,90,2))
        self.assertEqual(Document.from_chart(chart).chart(),chart)
    def test_versions_and_ambiguous_units_rejected(self):
        data=Document().project()
        for change in ({'version':7},{'coordinateScale':1},{'minReaderVersion':'0.13.0'},{'minReaderVersion':'invalid'},{'version':5}):
            with self.assertRaises(ValueError):Document.from_project(dict(data,**change))
        compatible=dict(data,appVersion='0.13.0',minReaderVersion='0.12.0');self.assertEqual(Document.from_project(compatible).lines[0].frames[0]['x'],.18)
    def test_agent_uses_public_units_in_both_directions(self):
        s=EditSession(Document());s.call('set_track_events',dict(line_id='line1',channel='x',events=[dict(start=0,end=4,**{'from':20,'to':80},ease='linear')]))
        self.assertAlmostEqual(s.doc.lines[0].value('x',2),.5);self.assertEqual(s.call('get_track',dict(line_id='line1'))['events']['x'][0]['to'],80)
        s.call('set_region_center',dict(region_index=0,rect_index=0,events=[dict(start=0,end=4,**{'from':[25,75],'to':[25,25]},ease='linear')]))
        self.assertEqual(s.doc.regions[0].events[0]['center'][0]['from'],[.25,.75]);self.assertEqual(s.call('get_region',dict(region_index=0,rect_index=0))['events']['center'][0]['from'],[25,75])

if __name__=='__main__':unittest.main()
