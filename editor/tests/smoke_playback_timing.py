"""Measure real playback: smooth frames and complete bars at different BPM/rates."""
import os,sys,time,json,statistics
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'editor'))
from main import QApplication,Editor
from model import Document,atomic_json
from track_editor import TrackDialog
from PySide6.QtCore import QTimer
app=QApplication([]);app.setApplicationName('IntervalPlaybackTimingTests');w=Editor(False);w.resize(1440,940);w.show();w.output.setVolume(0)
source=json.loads((ROOT/'app/src/main/assets/at-flow.json').read_text(encoding='utf-8'));reports=[]
def wait_until(fn,timeout=12):
    end=time.monotonic()+timeout
    while not fn() and time.monotonic()<end:app.processEvents();time.sleep(.001)
    assert fn(),w.statusBar().currentMessage()
def crossing(records,beat):
    for (a,x),(b,y) in zip(records,records[1:]):
        if x<=beat<=y and y>x:return a+(b-a)*(beat-x)/(y-x)
    raise AssertionError(('no crossing',beat,records[-3:]))
try:
    for bpm,rate,modal in [(120,1,False),(202,1,True),(120,.5,True),(202,.75,False)]:
        doc=Document.from_chart(source,str(ROOT/'app/src/main/assets/desultory-signals.ogg'));doc.retime(bpm,False)
        w.replace_document(doc,None);wait_until(lambda:w.hit_audio.mix_ready)
        w.scroll_speed.setValue(2.4);w.player.setPlaybackRate(rate);d=TrackDialog(w) if modal else None
        if d:d.open();app.processEvents()
        w.seek(16);records=[];paints=[];canvas=d.timeline if d else w.timeline;original=canvas.paintEvent
        def paint(event):
            start=time.perf_counter();original(event);paints.append((time.perf_counter()-start)*1000)
        canvas.paintEvent=paint
        def frame():
            if w.playing():records.append((time.perf_counter(),w.cursor))
        w.frameRendered.connect(frame);w.toggle_play();wait_until(lambda:w.cursor>=24.6,15)
        w.hit_audio.pause();w.frameRendered.disconnect(frame);canvas.paintEvent=original
        stable=[point for point in records if point[1]>=18];ratio=sum(b[1]>a[1]+.00001 for a,b in zip(stable,stable[1:]))/max(1,len(stable)-1)
        bar=crossing(records,24)-crossing(records,20);expected=240/bpm/rate
        assert abs(bar-expected)<.05,(bpm,rate,bar,expected)
        assert ratio>.93,(bpm,rate,ratio)
        assert abs(w.clock.seconds()-w.player.position()/1000)<.16
        frozen=w.cursor;deadline=time.perf_counter()+.12
        while time.perf_counter()<deadline:app.processEvents();time.sleep(.001)
        assert w.cursor==frozen
        reports.append(dict(bpm=bpm,rate=rate,page='four lanes' if modal else 'main',expectedBarSeconds=expected,measuredBarSeconds=bar,changingFrameRatio=ratio,paintMedianMs=statistics.median(paints),paintMaxMs=max(paints),frames=len(records)))
        print(reports[-1],flush=True)
        if d:d.reject()
    atomic_json(ROOT/'build/playback-timing.json',reports)
    print('PASS: real audio, smooth cursor, exact bar duration, independent zoom, main/four lanes, 0.5/0.75/1 rate and frozen pause')
finally:w.dirty=False;w.region_dirty=False;w.close()
