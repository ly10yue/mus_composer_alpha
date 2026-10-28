"""Verify actual audio gain, scroll geometry, timing independence and saved preferences."""
import os,sys,time,wave,array
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'editor'))
from main import QApplication,Editor
from model import Document
from agent_tools import fingerprint
from PySide6.QtTest import QTest
app=QApplication([]);app.setApplicationName('IntervalPreviewControlTests');w=Editor(False);w.resize(1440,940);w.show()
doc=Document();note=doc.add(4,'line1');w.replace_document(doc,None);w.seek(2);baseline=fingerprint(w.doc)
def until(fn):
    end=time.monotonic()+5
    while not fn() and time.monotonic()<end:QTest.qWait(10)
    assert fn()
try:
    until(w.hit_audio.bank.ready)
    w.hit_volume.setValue(100);assert w.hit_audio.bank.volume==1
    w.hit_volume.setValue(200);assert '200%' in w.hit_volume_label.text() and w.hit_audio.bank.volume==2
    import numpy as np
    from pcm_preview import mix_pcm
    music=np.zeros((4800,2),dtype='<i2');sound=w.hit_audio.bank.samples['tap']
    normal,_=mix_pcm(music,[(0,'tap',1)],w.hit_audio.bank.samples,1)
    boost,_=mix_pcm(music,[(0,'tap',2)],w.hit_audio.bank.samples,1)
    quiet=np.abs(sound)<.44
    assert np.max(np.abs(boost[:len(sound),0][quiet].astype(int)-2*normal[:len(sound),0][quiet].astype(int)))<=1
    w.scroll_speed.setValue(1);QTest.qWait(30);line=w.timeline.judgement_y();y1=w.timeline.beat_y(note.beat)
    image1=w.stage.grab().toImage();frame=w.stage.frame();field=w.stage.field();x=round(field.left()+w.doc.note_x(note)*field.width())
    def bar_y(image):
        rows=[y for y in range(round(frame.top()+3),round(frame.top()+frame.height()*.8-8)) if image.pixelColor(x,y).name()=='#a6f4cf']
        assert rows;return sum(rows)/len(rows)
    p1=bar_y(image1)
    w.scroll_speed.setValue(2);QTest.qWait(30);y2=w.timeline.beat_y(note.beat);p2=bar_y(w.stage.grab().toImage());stage_line=frame.top()+frame.height()*.8
    assert w.timeline.judgement_y()==line and abs((line-y2)-2*(line-y1))<1e-6
    assert abs((stage_line-p2)-2*(stage_line-p1))<3
    assert w.player.playbackRate()==1 and fingerprint(w.doc)==baseline
    w.save_preview_options();w.dirty=False;w.close();other=Editor(False)
    assert other.hit_volume.value()==200 and other.scroll_speed.value()==2
    other.dirty=False;other.close()
    print('PASS: real 200% PCM gain without clipping, timeline + game preview scroll x2, fixed judgement line, unchanged music/chart timing, saved settings')
finally:w.dirty=False;w.region_dirty=False;w.close()
