"""Qt fallback resampling, pending play and rapid replacement of a decoding source."""
import os,sys,time,wave,copy
from pathlib import Path
import numpy as np
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'editor'))
from main import QApplication,Editor
from model import Document
app=QApplication([]);app.setApplicationName('IntervalPcmSourceTests');w=Editor(False);w.output.setVolume(0)
path=ROOT/'build/editor-tests/mono-44100.wav';path.parent.mkdir(parents=True,exist_ok=True)
with wave.open(str(path),'wb') as f:
    f.setparams((1,2,44100,0,'NONE','not compressed'));f.writeframes(np.zeros(44100*2,dtype='<i2').tobytes())
def until(fn):
    end=time.monotonic()+10
    while not fn() and time.monotonic()<end:app.processEvents();time.sleep(.002)
    assert fn(),(w.cursor,w.hit_audio.mix_ready,w.statusBar().currentMessage())
try:
    w.hit_enabled.setChecked(True);w.hit_volume.setValue(100)
    # Replace a decoding song immediately: stale worker results must be ignored.
    w.replace_document(Document(audio=str(ROOT/'app/src/main/assets/desultory-signals.ogg')),None)
    doc=Document(bpm=120,duration=2,audio=str(path));doc.add(.5,'line1');doc.add(.75,'line2')
    w.replace_document(doc,None);w.toggle_play()
    until(lambda:w.hit_audio.mix_ready and w.cursor>.6)
    assert w.hit_audio.music.shape[1]==2 and abs(len(w.hit_audio.music)-96000)<32
    w.hit_audio.pause()
    with wave.open(str(w.hit_audio.mix_path),'rb') as f:
        pcm=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2)
    assert np.flatnonzero(pcm[:,0])[0]==12001
    w.hit_volume.setValue(200);w.seek(1);w.toggle_play();w.toggle_play()
    until(lambda:w.hit_audio.mix_ready)
    assert not w.playing() and abs(w.cursor-1)<.01
    previous=w.hit_audio.current_signature;draft=copy.deepcopy(w.doc);draft.add(1.5,'line3')
    w.hit_audio.active_doc=lambda:draft
    w.toggle_play();until(lambda:w.hit_audio.mix_ready and w.cursor>1.6);w.toggle_play()
    assert previous!=w.hit_audio.current_signature
    print('PASS: stale decode discarded, 44.1k mono resampling, sample-aligned heads, pending-play cancellation, position preservation and draft preview')
finally:w.dirty=False;w.region_dirty=False;w.close()
