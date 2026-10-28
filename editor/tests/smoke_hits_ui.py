"""Exercise the actual shared PCM source and real media playback transport."""
import os,sys,time
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'editor'))
from main import QApplication,Editor
from model import Document
from PySide6.QtTest import QTest
app=QApplication([]);app.setApplicationName('IntervalHitTests');w=Editor(False);w.show();w.output.setVolume(0)
w.hit_enabled.setChecked(True);w.hit_volume.setValue(150)
doc=Document(bpm=120,duration=150.750667,audio=str(ROOT/'app/src/main/assets/desultory-signals.ogg'))
for beat,line,length in [(.5,'line1',0),(1,'line2',0),(1.5,'line1',1),(2,'line3',0),(2,'line4',0),(3,'line2',0)]:doc.add(beat,line,length)
w.replace_document(doc,None);events=[];w.hit_audio.bank.triggered.connect(lambda ident,hold:events.append((ident,hold)))
def wait(ms):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.002)
def until(fn,timeout=10000):
    end=time.monotonic()+timeout/1000
    while not fn() and time.monotonic()<end:wait(10)
    assert fn(),(w.cursor,events,w.statusBar().currentMessage())
try:
    until(lambda:w.audio_loaded and w.hit_audio.mix_ready);assert Path(w.player.source().toLocalFile())==w.hit_audio.mix_path
    assert w.hit_audio.mix_path.stat().st_size>1000000
    w.toggle_play();until(lambda:w.cursor>3.2);w.toggle_play()
    assert sorted(i for i,h in events)==list(range(6)) and sum(h for i,h in events)==1,events
    count=len(events);wait(200);assert len(events)==count
    w.toggle_play();wait(180);w.toggle_play();assert len(events)==count
    events.clear();w.seek(1.25);w.toggle_play();until(lambda:w.cursor>3.2);w.toggle_play();assert sorted(i for i,h in events)==[2,3,4,5],events
    events.clear();w.hit_enabled.setChecked(False);w.seek(0);w.toggle_play();until(lambda:w.cursor>1.2);assert not events
    w.hit_enabled.setChecked(True);until(lambda:w.cursor>3.2);w.toggle_play();assert sorted(i for i,h in events)==[2,3,4,5],events
    events.clear();w.loop_a=1.25;w.loop_b=2.25;w.loop_check.setChecked(True);w.seek(1.25);w.toggle_play();until(lambda:sum(i==2 for i,h in events)>=3);w.toggle_play();assert all(i in (2,3,4) for i,h in events),events
    w.loop_check.setChecked(False)
    for rate in [.5,.75,1.]:
        events.clear();w.player.setPlaybackRate(rate);w.seek(1.8);w.toggle_play();until(lambda:w.cursor>2.2);w.toggle_play()
        assert sorted(i for i,h in events)==[3,4],(rate,events)
        assert Path(w.player.source().toLocalFile())==w.hit_audio.mix_path
    w.metronome.setChecked(True);until(lambda:w.hit_audio.mix_ready)
    assert any(kind=='bar' for seconds,kind,gain in w.hit_audio.snapshot()[1])
    w.hit_volume.setValue(200);until(lambda:w.hit_audio.mix_ready)
    assert w.hit_audio.bank.volume==2
    print('PASS: shared PCM file, head count, chords, pause/resume, seek, mute/re-enable, loop, 0.5/0.75/1 speed, metronome and gain rebuild')
finally:
    w.player.pause();w.hit_audio.bank.stop();w.dirty=False;w.region_dirty=False;w.close()
