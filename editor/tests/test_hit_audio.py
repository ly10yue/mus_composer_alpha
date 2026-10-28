import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hit_audio import HitTimeline
from model import Note

class HitTimelineTests(unittest.TestCase):
    def test_heads_chords_and_no_hold_tail_duplicates(self):
        notes=[Note(0,1,'line1'),Note(1,2,'line2',2),Note(2,2,'line3')];clock=HitTimeline();clock.reset(notes,0)
        self.assertEqual(clock.due(.99,1),[])
        self.assertEqual([n.id for n in clock.due(1,1)],[0]);self.assertEqual(clock.due(1,1),[])
        self.assertEqual([n.id for n in clock.due(2,1)],[1,2]);self.assertEqual(clock.due(4,1),[])
    def test_seek_and_loop_replay_only_future_heads(self):
        notes=[Note(i,i,'line1') for i in range(5)];clock=HitTimeline();clock.reset(notes,2)
        self.assertEqual([n.id for n in clock.due(2,1)],[2])
        clock.reset(notes,2.5);self.assertEqual([n.id for n in clock.due(3,1)],[3])
        clock.reset(notes,1);self.assertEqual([n.id for n in clock.due(1,1)],[1])
    def test_stall_drops_old_events_instead_of_burst(self):
        clock=HitTimeline();clock.reset([Note(i,i/10,'line1') for i in range(40)],0)
        self.assertEqual([n.id for n in clock.due(3,.11)],[29,30]);self.assertEqual(clock.due(3,.11),[])

if __name__=='__main__':unittest.main()
