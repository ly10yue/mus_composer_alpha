import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playback_clock import PlaybackClock

class PlaybackClockTests(unittest.TestCase):
    def setUp(self):
        self.wall=0.;self.clock=PlaybackClock(lambda:self.wall)
    def test_coarse_reports_interpolate_without_accumulating_drift(self):
        c=self.clock;c.start(0,1);previous=0;changes=0;samples=0
        for i in range(1,60001):
            self.wall=i/100;c.observe(int(self.wall/.085)*.085);value=c.seconds()
            self.assertGreaterEqual(value,previous)
            if self.wall>1:
                self.assertLess(abs(value-self.wall),.025);samples+=1;changes+=value>previous+.001
            previous=value
        self.assertGreater(changes/samples,.99)
    def test_bpm_and_zoom_do_not_double_multiply_time(self):
        c=self.clock;c.start(0,1)
        for i in range(1,401):self.wall=i/100;c.observe(int(self.wall/.085)*.085);c.seconds()
        for bpm in (60,120,202):self.assertAlmostEqual(c.beat(bpm,0),4*bpm/60,delta=.04)
        self.assertAlmostEqual(c.beat(120,.25),7.5,delta=.04)
    def test_pause_rate_seek_and_stalled_audio(self):
        c=self.clock;c.start(0,1);self.wall=.1;c.observe(.1);self.wall=.15
        value=c.seconds();c.pause();self.wall=5;self.assertEqual(c.seconds(),value)
        c.reset(10,True,.5);self.wall=5.1;c.observe(10.05);self.wall=5.2;self.assertAlmostEqual(c.seconds(),10.1)
        before=c.seconds();c.set_rate(1);self.assertEqual(c.seconds(),before)
        self.wall=5.25;self.assertAlmostEqual(c.seconds(),before+.05)
        c.reset(30,True);c.observe(10);self.assertEqual(c.seconds(),30)
        self.wall=5.35;c.observe(30.1);self.wall=20;self.assertLessEqual(c.seconds(),30.25)

if __name__=='__main__':unittest.main()
