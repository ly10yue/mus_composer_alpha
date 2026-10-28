"""0.12 authoring workflow, edge panning and union-only border pixels."""
import os,sys,copy,math,json
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'editor'))
from PySide6.QtCore import Qt,QPoint,QPointF,QTimer
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtTest import QTest
from main import QApplication,Editor,STYLE
from region_editor import RegionDialog
from track_editor import TrackDialog
from model import Document
from views import Stage
app=QApplication([]);app.setApplicationName('Interval012Tests');app.setStyleSheet(STYLE);QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc');app.setFont(QFont('Microsoft YaHei UI',10))
w=Editor(False);w.resize(1440,940);w.show();checks=[];failures=[]
def check(value,name):
    assert value,name
    checks.append(name)
def pan(canvas):
    owner=canvas.window;w.seek(4);owner.doc.division=4;owner.doc.grid_unit='beat';canvas.ppb=64;canvas.sync();v=canvas.viewport();QTest.qWait(40)
    start=QPoint(round(canvas.ruler+50),round(canvas.beat_y(4)));outside=QPoint(start.x(),-15)
    original=canvas.y_beat(start.y());QTest.mousePress(v,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ControlModifier,start);QTest.mouseMove(v,outside,20);QTest.qWait(400)
    check(w.cursor>4,'Ctrl near top advances timeline');check(abs(canvas.edge.anchor[1]-original)<1e-6,'marquee anchor stays at original musical time')
    QTest.mouseMove(v,QPoint(start.x(),v.height()+20),20);before=w.cursor;QTest.qWait(220);check(w.cursor<before,'Ctrl below bottom reverses timeline')
    QTest.mouseRelease(v,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ControlModifier,QPoint(start.x(),v.height()+20));before=w.cursor;QTest.qWait(160);check(w.cursor==before and not canvas.edge.timer.isActive(),'release stops panning')
try:
    doc=Document();doc.lines[0].frames[0]['x']=.5;doc.add(4,'line1');w.replace_document(doc,None);w.scroll_speed.setValue(1);pan(w.timeline)
    baseline=copy.deepcopy(w.doc.project())
    def region_actions():
        d=app.activeModalWidget()
        try:
            check(isinstance(d,RegionDialog),'direct region entry');d.add_line();check(d.track.base('center')==[.5,.5] and d.track.base('angle')==0 and d.track.base('width')==1 and not d.track.events,'new full-screen region defaults')
            d.name.setText('第二判定区');d.rename();d.create_interval('center',0,4);d.value_from.setValue(25);d.from_y.setValue(75);d.value_to.setValue(75);d.to_y.setValue(25);d.write()
            check(d.track.events['center'][0]['to']==[.75,.25],'0–100 input conversion');pan(d.timeline)
            d.delete_line();check(len(d.region.rects)==1,'delete region');d.undo();check(len(d.region.rects)==2 and d.region.names[1]=='第二判定区','undo restores region and name')
            d.select_line(1);d.resize(1400,880);w.seek(2);d.select(('center',0));QTest.qWait(60)
            screens=ROOT/'docs/screenshots/012';screens.mkdir(parents=True,exist_ok=True);d.grab().save(str(screens/'regions.png'))
            d.resize(1024,640);QTest.qWait(60);d.grab().save(str(screens/'regions-compact.png'));d.accept()
        except BaseException as e:failures.append(e);d.reject()
    QTimer.singleShot(60,region_actions);w.edit_regions()
    if failures:raise failures[0]
    check(len(w.doc.regions[0].rects)==2 and not w.region_dirty,'one-step direct commit');check(w.agent_panel.target()['rect_index']==1,'selected region becomes Agent target');w.undo();check(w.doc.project()==baseline,'whole dialog undo');w.redo()
    def line_actions():
        d=app.activeModalWidget()
        try:
            d.create_interval('x',0,4);d.value_from.setValue(20);d.value_to.setValue(80);d.write();check(d.track.value('x',2)==.5,'line 0–100 UI');pan(d.timeline);d.reject()
        except BaseException as e:failures.append(e);d.reject()
    QTimer.singleShot(60,line_actions);w.edit_tracks()
    if failures:raise failures[0]
    # Border at x=.4 lies inside the first rectangle and must disappear.
    d=Document();d.regions[0].rects=[[.1,.2,.6,.7],[.4,.2,.9,.7]]
    for t in d.lines:t.frames[0]['alpha']=0
    w.replace_document(d,None);w.seek(0);stage=w.stage;stage.editing=False;stage.resize(480,300);QTest.qWait(60);im=stage.grab().toImage();f=stage.field();y=round(f.top()+f.height()*.4)
    at=lambda x:im.pixelColor(round(f.left()+f.width()*x),y)
    check(at(.4)==at(.5),'overlap interior has no drawn edge');check(at(.1).green()>at(.4).green()+30,'outer boundary remains visible')
    stage.grab().save(str(ROOT/'docs/screenshots/012/union.png'))
    (ROOT/'docs/012-ui-tests.json').write_text(json.dumps(dict(ok=True,checks=checks),ensure_ascii=False,indent=2),encoding='utf-8');print('PASS',len(checks),'UI checks')
finally:w.dirty=False;w.region_dirty=False;w.close()
