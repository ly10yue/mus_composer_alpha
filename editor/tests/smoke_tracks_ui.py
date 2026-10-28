"""Four-lane authoring gestures, isolated draft commit, v4 export and parity."""
import copy,json,os,sys,time
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'editor'))
from PySide6.QtCore import Qt,QTimer,QPoint,QPointF
from PySide6.QtGui import QFont,QFontDatabase,QWheelEvent
from PySide6.QtTest import QTest
from main import QApplication,Editor,STYLE
from track_editor import TrackDialog
from model import Document,export_package,atomic_json
app=QApplication([]);app.setApplicationName('IntervalTrackTests');app.setStyleSheet(STYLE)
QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc');app.setFont(QFont('Microsoft YaHei UI',10))
w=Editor(False);w.resize(1440,940);w.show();w.output.setVolume(0)
doc=Document(title='Four lanes / interval events',bpm=120,duration=150.750667,audio=str(ROOT/'app/src/main/assets/desultory-signals.ogg'))
doc.lines[0].frames=[dict(beat=0.,x=.18,alpha=1.,ease='linear'),dict(beat=8.,x=.3,alpha=.4,ease='linear')]
doc.add(2,'line4');doc.add(4,'line1',6);doc.add(12,'line1');w.replace_document(doc,None)
screens=ROOT/'docs/screenshots/track-events';screens.mkdir(parents=True,exist_ok=True);failures=[]
def edit_dialog():
    d=app.activeModalWidget()
    try:
        assert isinstance(d,TrackDialog);d.resize(1400,880);d.zoom.setValue(1);w.seek(0);QTest.qWait(40)
        d.delete_line();assert len(d.doc.lines)==4 and '仍有音符' in d.hint.text()
        d.add_line();assert len(d.doc.lines)==5 and d.track.pose(0)==(.5,0) and d.track.value('speed',0)==1
        canvas=d.timeline;v=canvas.viewport()
        def point(col,beat):return QPoint(round(canvas.lane(col).center().x()),round(canvas.beat_y(beat)))
        def drag(col,a,b):
            QTest.mousePress(v,Qt.MouseButton.LeftButton,pos=point(col,a));QTest.mouseMove(v,point(col,b),30);QTest.mouseRelease(v,Qt.MouseButton.LeftButton,pos=point(col,b))
        d.set_tool('tap');QTest.mouseClick(v,Qt.MouseButton.LeftButton,pos=point(0,2))
        d.set_tool('hold');drag(0,4,6);assert len(d.doc.notes)==5 and d.doc.notes[-1].line==d.track.id and d.doc.notes[-1].length==2
        d.undo();d.undo();assert len(d.doc.notes)==3;d.delete_line();assert len(d.doc.lines)==4
        d.lines.setCurrentIndex(0);d.name.setText('四栏演示');d.rename();d.set_tool('select')
        d.select(('x',0));d.start.setValue(0);d.end.setValue(4);d.value_from.setValue(20);d.value_to.setValue(70);d.ease.setCurrentIndex(0);QTest.mouseClick(d.write_button,Qt.MouseButton.LeftButton)
        drag(1,4.25,6.75);assert len(d.track.events['x'])==2
        d.start.setValue(4);d.end.setValue(8);d.value_from.setValue(70);d.value_to.setValue(25);d.ease.setCurrentIndex(1);d.write()
        before=copy.deepcopy(d.track.events['x']);assert not d.create_interval('x',1,3) and d.track.events['x']==before
        d.select(('alpha',0));d.value_from.setValue(0);d.value_to.setValue(1);d.ease.setCurrentIndex(2);d.write()
        drag(3,2,6);d.value_from.setValue(1);d.value_to.setValue(2);d.ease.setCurrentIndex(3);d.write()
        # Endpoint resize and whole-strip movement on the speed lane.
        drag(3,6,6.5);assert d.track.events['speed'][0]['end']==6.5
        drag(3,4,4.25);assert d.track.events['speed'][0]['start']==2.25
        d.undo();d.undo();assert d.track.events['speed'][0]['start']==2 and d.track.events['speed'][0]['end']==6
        d.create_interval('speed',8,9);d.value_from.setValue(0);d.value_to.setValue(0);d.write()
        d.create_interval('speed',9,10);d.value_from.setValue(.5);d.value_to.setValue(1);d.write()
        d.select(('notes',2));d.start.setValue(11.5);d.end.setValue(11.5);d.write();assert d.doc.notes[-1].beat==11.5 and w.doc.notes[-1].beat==12
        # Both normal wheels and pixel scrolling move the chart down / time forward.
        w.seek(2);fixed=canvas.judgement_y()
        event=QWheelEvent(QPointF(250,200),QPointF(v.mapToGlobal(QPoint(250,200))),QPoint(),QPoint(0,120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
        QApplication.sendEvent(v,event);assert abs(w.cursor-2.25)<1e-6 and canvas.judgement_y()==fixed
        for size,name in [((1400,880),'wide'),((1024,640),'compact')]:
            d.resize(*size);d.zoom.setValue(.65 if name=='compact' else 1);w.seek(3);d.select(('x',1));QTest.qWait(90);d.grab().save(str(screens/('editor-'+name+'.png')))
        d.accept()
    except BaseException as error:failures.append(error);d.reject()
QTimer.singleShot(100,edit_dialog);w.edit_tracks()
try:
    if failures:raise failures[0]
    assert w.doc.notes[-1].beat==11.5 and w.doc.lines[0].events['speed'];w.undo();assert w.doc.notes[-1].beat==12 and not w.doc.lines[0].events;w.redo()
    before=copy.deepcopy(w.doc.project())
    def cancel():
        d=app.activeModalWidget();d.add_line();d.add_note(3);d.reject()
    QTimer.singleShot(70,cancel);w.edit_tracks();assert w.doc.project()==before
    w.seek(5.5)
    for aspect,name in [(0,'16x9'),(1,'4x3')]:
        w.set_aspect(aspect);QTest.qWait(50);w.stage.grab().save(str(screens/('preview-'+name+'.png')))
    out=ROOT/'build/editor-tests';out.mkdir(parents=True,exist_ok=True);w.path=out/'tracks.ivproj';assert w.save();export_package(w.doc,out/'tracks.interval')
    chart=w.doc.chart('music.ogg');assert chart['version']==6 and all('x' not in n for n in chart['notes'])
    parity=[]
    for t in w.doc.lines:
        for now in [0,.25,1,2,3,3.5,4,5.5,6,8,8.5,9,10,11,14]:
            for arrival in [now-.5,now,now+.2,now+1,now+2,now+4]:
                parity.append(dict(line=t.id,now=w.doc.seconds(now),arrival=w.doc.seconds(arrival),x=t.x_at(now,arrival),alpha=t.pose(now)[1],speed=t.value('speed',now),distance=w.doc.seconds(t.distance(now,arrival))))
    atomic_json(out/'tracks-parity.json',parity)
    w.open_path(out/'tracks.interval');assert w.doc.chart('music.ogg')==chart
    deadline=time.monotonic()+8
    while not w.hit_audio.mix_ready and time.monotonic()<deadline:app.processEvents();time.sleep(.003)
    w.seek(4.5);w.toggle_play();QTest.qWait(450);w.toggle_play();assert w.cursor>5
    w.dirty=True;w.autosave();assert json.loads(w.recovery_path.read_text(encoding='utf-8'))['version']==6
    print('PASS: four lanes, defaults, note/interval gestures, values/eases, overlap rejection, resize/move, wheel, undo/redo/cancel, compact/wide UI, v4 roundtrip, real playback')
finally:w.dirty=False;w.region_dirty=False;w.close()
