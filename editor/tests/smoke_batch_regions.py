"""Real Qt gestures: region lanes, multi-selection, exact paste and wheel grids."""
import copy,json,os,sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'editor'))
from PySide6.QtCore import Qt,QPoint,QPointF,QTimer
from PySide6.QtGui import QWheelEvent,QFont,QFontDatabase
from PySide6.QtTest import QTest
from main import QApplication,Editor,STYLE
from track_editor import TrackDialog
from region_editor import RegionDialog
from model import Document,DIVISIONS,export_package,atomic_json
from motion import polygon
app=QApplication([]);app.setApplicationName('IntervalRegionBatchTests');app.setStyleSheet(STYLE);QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc');app.setFont(QFont('Microsoft YaHei UI',10))
w=Editor(False);w.resize(1440,940);w.show();w.output.setVolume(0)
doc=Document(audio=str(ROOT/'app/src/main/assets/desultory-signals.ogg'),duration=150.750667);doc.lines[0].frames[0]['x']=.5
doc.add(1,'line1');doc.add(2,'line1',1);w.replace_document(doc,None);w.scroll_speed.setValue(1)
screens=ROOT/'docs/screenshots/region-events';screens.mkdir(parents=True,exist_ok=True)
checks=0
def check(ok,message):
    global checks
    checks+=1
    assert ok,message
def key(widget,k,mods=Qt.KeyboardModifier.ControlModifier):widget.setFocus();QTest.keyClick(widget,k,mods);app.processEvents()
def marquee(canvas,left,top,right,bottom):
    v=canvas.viewport();a=QPoint(round(left),round(top));b=QPoint(round(right),round(bottom))
    QTest.mousePress(v,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ControlModifier,a);QTest.mouseMove(v,b,20);QTest.mouseRelease(v,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ControlModifier,b);app.processEvents()
def wheels(canvas,dialog=None):
    v=canvas.viewport()
    for unit in ('beat','bar'):
        for div in DIVISIONS:
            owner=dialog or w;owner.doc.grid_unit=unit;owner.doc.division=div;w.seek(10);step=owner.doc.step
            for delta in (120,-120,30,30,30,30):
                e=QWheelEvent(QPointF(200,100),QPointF(v.mapToGlobal(QPoint(200,100))),QPoint(),QPoint(0,delta),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
                QApplication.sendEvent(v,e)
                if delta==120:check(abs(w.cursor-(10+step))<1e-7,'one notch = one grid')
                if delta==-120:check(abs(w.cursor-10)<1e-7,'reverse one grid')
            check(abs(w.cursor-(10+step))<1e-7,'high-resolution wheel accumulates exactly one notch')
    owner.doc.grid_unit='beat';owner.doc.division=4;w.seek(0)
failures=[]
def region_test():
    d=app.activeModalWidget()
    try:
        check(isinstance(d,RegionDialog),'region dialog opens');d.zoom.setValue(1);w.seek(0);QTest.qWait(30)
        canvas=d.timeline;v=canvas.viewport()
        def point(col,b):return QPoint(round(canvas.lane(col).center().x()),round(canvas.beat_y(b)))
        for col,prop in enumerate(d.PROPS):
            QTest.mousePress(v,Qt.MouseButton.LeftButton,pos=point(col,1));QTest.mouseMove(v,point(col,4),20);QTest.mouseRelease(v,Qt.MouseButton.LeftButton,pos=point(col,4))
            check(len(d.track.events[prop])==1,'drag creates region strip '+prop)
            d.value_from.setValue(50 if prop=='center' else 0 if prop=='angle' else 80);d.value_to.setValue(50 if prop=='center' else 90 if prop=='angle' else 60)
            if prop=='center':d.from_y.setValue(70);d.to_y.setValue(30)
            d.ease.setCurrentIndex(1);d.write()
        check(d.track.value('center',2.5)==[.5,.5],'center XY evaluated together')
        marquee(canvas,canvas.ruler+1,canvas.beat_y(4.3),v.width()-3,canvas.beat_y(.7));check(len(d.selection)==4,'all four lanes selected');check(d.delete_button.isEnabled(),'batch Delete button enabled')
        key(canvas,Qt.Key.Key_C);w.seek(8.123);key(canvas,Qt.Key.Key_V)
        check(len(d.selection)==4 and all(abs(d.track.events[p][1]['start']-8.123)<1e-8 for p in d.PROPS),'first strip aligns exactly with judgment line, no snapping')
        before=copy.deepcopy(d.doc.project());key(canvas,Qt.Key.Key_V);check(before==d.doc.project(),'overlapping paste is atomic')
        key(canvas,Qt.Key.Key_Delete,Qt.KeyboardModifier.NoModifier);check(all(len(d.track.events[p])==1 for p in d.PROPS),'batch delete four');d.undo();check(all(len(d.track.events[p])==2 for p in d.PROPS),'single undo restores batch')
        d.redo();wheels(canvas,d);w.seek(2);d.select(('center',0));QTest.qWait(30)
        for aspect,name in ((16/9,'16x9'),(4/3,'4x3')):
            d.stage.aspect=aspect;d.resize(1400,880);QTest.qWait(60);d.grab().save(str(screens/(name+'.png')))
        d.resize(1024,640);QTest.qWait(60);d.grab().save(str(screens/'compact.png'));d.accept()
    except BaseException as ex:failures.append(ex);d.reject()
try:
    wheels(w.timeline);w.seek(0);w.set_tool('tap');c=w.timeline
    marquee(c,c.ruler+1,c.beat_y(3.4),c.viewport().width()-25,c.beat_y(.6));check(len(w.selection)==2 and len(w.doc.notes)==2,'Ctrl box overrides tap tool')
    key(c,Qt.Key.Key_C);w.seek(10.123);key(c,Qt.Key.Key_V);check(min(n.beat for n in w.doc.notes if n.id in w.selection)==10.123,'main notes paste exact cursor');key(c,Qt.Key.Key_Delete,Qt.KeyboardModifier.NoModifier);w.undo();w.undo()
    w.tabs.setCurrentIndex(1);w.load_region_draft(w.doc.regions[0]);w.stage.selected=0;w.rect_selected()
    QTimer.singleShot(80,region_test);w.edit_motion()
    if failures:raise failures[0]
    check(w.region_dirty and w.stage.events[0]['width'],'draft receives events');w.apply_region();check(w.doc.chart()['version']==6,'region application emits v5')
    out=ROOT/'build/editor-tests';out.mkdir(parents=True,exist_ok=True);export_package(w.doc,out/'regions.interval');atomic_json(out/'regions.ivproj',w.doc.project())
    original=w.doc.chart();w.open_path(out/'regions.interval');check(w.doc.chart()==dict(original,audio='music.ogg'),'v6 package roundtrip')
    r=w.doc.regions[0];samples=[]
    for aspect in (1.1733333333,1.6177777778):
        for beat in (0,1,1.5,2.5,3.5,4,5):samples.append(dict(aspect=aspect,time=beat*60/w.doc.bpm,points=polygon(r.rects[0],r.motions[0] if r.motions else [],beat,aspect,r.events[0])))
    atomic_json(out/'regions-parity.json',samples)
    def tracks_test():
        d=app.activeModalWidget()
        try:
            d.index=0;d.changed();d.zoom.setValue(1);w.seek(0);d.create_interval('x',1,4);QTest.qWait(30);c=d.timeline
            marquee(c,c.ruler+1,c.beat_y(4.3),c.lane(1).right()-2,c.beat_y(.6));check(len(d.selection)==3,'mixed notes and line interval box')
            key(c,Qt.Key.Key_C);w.seek(10.123);key(c,Qt.Key.Key_V);check(len(d.selection)==3,'mixed paste');check(abs(min(start for k,start,end,data in c.items() if k in d.selection)-10.123)<1e-8,'mixed earliest item at line')
            key(c,Qt.Key.Key_Delete,Qt.KeyboardModifier.NoModifier);check(len(d.doc.notes)==2,'mixed deletion');d.undo();check(len(d.doc.notes)==4,'mixed undo');wheels(c,d);d.reject()
        except BaseException as ex:failures.append(ex);d.reject()
    QTimer.singleShot(80,tracks_test);w.edit_tracks()
    if failures:raise failures[0]
    atomic_json(ROOT/'docs/region-batch-tests.json',dict(ok=True,checks=checks,formats=[6],grids=list(DIVISIONS),screens=['16x9','4x3','compact']))
    print(f'PASS {checks}: region XY/angle/size curves, Ctrl marquee, mixed batch deletion/copy/paste, exact cursor alignment, atomic overlap rejection, undo, all grids, v6 package')
finally:
    QApplication.clipboard().clear();w.dirty=False;w.region_dirty=False;w.close()
