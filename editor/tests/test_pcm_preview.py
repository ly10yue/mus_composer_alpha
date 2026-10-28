"""Check actual PCM frame placement, including overlapping voices and chords."""
import sys,unittest,tempfile,wave
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pcm_preview import mix_pcm,render_mix,RATE,waveform_peaks

class PcmPreviewTests(unittest.TestCase):
    def test_background_waveform_includes_partial_bin_and_negative_peak(self):
        music=np.zeros((1000,2),dtype='<i2');music[2,0]=16384;music[-1,1]=-32768
        self.assertEqual(waveform_peaks(music),[.5,1.])
    def setUp(self):
        self.music=np.zeros((RATE,2),dtype='<i2')
        self.sounds={'tap':np.full(1600,.1,dtype=np.float32),'hold':np.full(2400,.2,dtype=np.float32)}
    def test_chord_same_frame_and_close_hits_overlap(self):
        events=[(.1,'tap',1),(.1,'hold',1),(.11,'tap',1),(.12,'tap',1)]
        pcm,placed=mix_pcm(self.music,events,self.sounds,1)
        self.assertEqual([p[0] for p in placed],[4800,4800,5280,5760])
        self.assertTrue(np.all(pcm[:4800]==0))
        for frame,expected in [(4800,.3),(5280,.4),(5760,.5)]:
            self.assertLessEqual(abs(int(pcm[frame,0])-round(32767*expected)),1)
        np.testing.assert_array_equal(pcm[:,0],pcm[:,1])
    def test_music_and_hit_share_sample_index_at_buffer_boundary(self):
        self.music[4096]=3277
        pcm,placed=mix_pcm(self.music,[(4096/RATE,'tap',1)],self.sounds,1,music_gain=1)
        self.assertEqual(placed[0][0],4096)
        self.assertAlmostEqual(pcm[4096,0]/32767,.2,places=4)
        self.assertEqual(pcm[4095,0],0)
    def test_offsets_gain_mute_and_end_clipping(self):
        pcm,placed=mix_pcm(self.music,[(-.01,'tap',2),(.999,'hold',0)],self.sounds,1)
        self.assertEqual(placed,[(0,1120,'tap'),(47952,48,'hold')])
        self.assertAlmostEqual(pcm[0,0]/32767,.2,places=4)
        self.assertEqual(pcm[-1,0],0)
    def test_overload_limits_without_moving_onset_and_wav_roundtrip(self):
        events=[(.2,'hold',2)]*12
        with tempfile.TemporaryDirectory() as directory:
            path=Path(render_mix(Path(directory)/'mixed.wav',self.music,events,self.sounds,1))
            with wave.open(str(path),'rb') as f:
                self.assertEqual((f.getframerate(),f.getnchannels(),f.getsampwidth()),(48000,2,2))
                pcm=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2)
        self.assertEqual(np.flatnonzero(pcm[:,0])[0],9600)
        self.assertLessEqual(int(pcm.max()),32767)
        self.assertGreater(pcm[9600,0],32000)

if __name__=='__main__':unittest.main()
