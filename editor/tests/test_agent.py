import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import Document
from agent_tools import EditSession,TOOLS,SCHEMAS,fingerprint,validate_schema
from motion import polygon
from agent_client import endpoint,initial_messages,skill_folder

def command():return dict(region_index=0,rect_index=0,start_beat=4,end_beat=12,start_rect=[0,50,50,100],end_rect=[0,0,50,50],start_angle=0,end_angle=0,ease='linear')

class AgentTests(unittest.TestCase):
    def test_example_geometry_and_isolation(self):
        original=Document(audio=__file__);session=EditSession(original,target=dict(region_index=0,rect_index=0))
        before=fingerprint(original);session.call('animate_region',command())
        self.assertEqual(fingerprint(original),before);self.assertEqual([(r.start,r.end) for r in session.doc.regions],[(0,4),(4,12),(12,126)])
        r=session.doc.region_at(8);points=polygon(r.rects[0],r.motions[0],8,1.6)
        self.assertAlmostEqual(min(y for x,y in points),.25);self.assertEqual(min(x for x,y in points),0);self.assertEqual(max(x for x,y in points),.5)
        self.assertEqual(session.doc.region_at(12).rects,[[0,0,1,1]])
    def test_sibling_region_frames_preserved(self):
        d=Document();frames=[dict(beat=0,x=0,y=0,angle=0,ease='linear'),dict(beat=16,x=.1,y=.1,angle=30,ease='smooth')]
        d.set_region(0,16,[[0,0,.4,.4],[.6,.6,.9,.9]],'two',[[],frames]);s=EditSession(d);s.call('animate_region',command())
        for b in (0,8,14):self.assertEqual(s.doc.region_at(b).motions[1],frames)
        self.assertEqual(s.doc.region_at(8).rects[1],[.6,.6,.9,.9])
    def test_invalid_tools_atomic(self):
        s=EditSession(Document());before=fingerprint(s.doc)
        for name,args in [('exec',{}),('animate_region',{**command(),'region_index':999}),('animate_region',{**command(),'end_rect':[0,0,-.4,.4]}),('animate_region',{**command(),'end_beat':200}),('animate_region',{**command(),'script':'bad'}),('set_track',dict(line_id='bad',name='x',frames=[]))]:
            with self.assertRaises(ValueError):s.call(name,args)
            self.assertEqual(fingerprint(s.doc),before);self.assertEqual(s.operations,[])
    def test_invalid_notes_rollback_whole_batch(self):
        s=EditSession(Document());before=fingerprint(s.doc)
        with self.assertRaises(ValueError):s.call('edit_notes',dict(notes=[dict(id=None,beat=4,line='line1',length=0),dict(id=99,beat=6,line='line1',length=0)]))
        self.assertEqual(fingerprint(s.doc),before)
    def test_notes_bindings_update_delete(self):
        s=EditSession(Document());result=s.call('edit_notes',dict(notes=[dict(id=None,beat=4+1/6,line='line1',length=0),dict(id=None,beat=8,line='line2',length=2)]));ids=result['changed_ids']
        self.assertEqual(s.doc.notes[0].beat,4+1/6)
        s.call('edit_notes',dict(notes=[dict(id=ids[0],beat=5,line='line3',length=0)]));self.assertEqual(s.doc.notes[0].line,'line3')
        s.call('delete_notes',dict(ids=[ids[1]]));self.assertEqual(len(s.doc.notes),1)
    def test_track_and_queries(self):
        s=EditSession(Document());s.call('set_track',dict(line_id='new',name='NEW',frames=[dict(beat=0,x=.3,alpha=.5,ease='linear')]))
        self.assertEqual(s.call('get_track',dict(line_id='new'))['frames'][0]['alpha'],.5)
        self.assertEqual(s.call('list_regions',dict(offset=0,limit=1))['total'],1)
        self.assertEqual(s.call('get_notes',dict(start_beat=0,end_beat=8,offset=0,limit=1))['notes'],[])
        with self.assertRaises(ValueError):s.call('get_region',dict(region_index=0,rect_index=1))
    def test_context_has_no_paths_and_skill_is_loaded(self):
        d=Document(audio='C:/private/song.ogg');s=EditSession(d);messages=initial_messages(s,'移动区域')
        body=json.dumps(messages,ensure_ascii=False);self.assertNotIn(d.audio,body);self.assertNotIn('api_key',body)
        self.assertIn('(N-1)*meter',body);self.assertIn('animate_region',body)
        self.assertEqual(json.loads((skill_folder()/'references/tool-schema.json').read_text(encoding='utf-8')),TOOLS)
    def test_strict_schema_recurses(self):
        def check(schema):
            if schema['type']=='object':
                self.assertFalse(schema['additionalProperties']);self.assertEqual(set(schema['required']),set(schema['properties']))
                for child in schema['properties'].values():check(child)
            elif schema['type']=='array':check(schema['items'])
        for schema in SCHEMAS.values():check(schema)
        for bad in (float('nan'),True,'4'):
            with self.assertRaises(ValueError):validate_schema({**command(),'start_beat':bad},SCHEMAS['animate_region'])
    def test_url_rules(self):
        self.assertEqual(endpoint('https://api.openai.com/v1/'),'https://api.openai.com/v1/chat/completions')
        self.assertEqual(endpoint('http://127.0.0.1:1234/v1/chat/completions'),'http://127.0.0.1:1234/v1/chat/completions')
        for bad in ('http://example.com/v1','https://name:secret@example.com/v1','https://example.com/v1?key=secret','file:///etc/passwd'):
            with self.assertRaises(ValueError):endpoint(bad)
    def test_cross_segment_requires_explicit_replacement(self):
        d=Document();d.set_region(8,16,[[.5,0,1,1]],'right');s=EditSession(d)
        with self.assertRaises(ValueError):s.call('animate_region',command())
        s.call('set_region',dict(start_beat=4,end_beat=12,label='left',rects=[[0,0,.5,1]],motions=[]))
        self.assertEqual(s.doc.region_at(10).label,'left');self.assertEqual(s.doc.region_at(14).label,'right')

if __name__=='__main__':unittest.main()
