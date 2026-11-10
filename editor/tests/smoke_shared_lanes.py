"""Exercise both canvases in the workspace that users actually edit."""
import os,sys,time
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'editor'))
from PySide6.QtCore import Qt,QPoint,QRectF,QTimer
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtTest import QTest
from main import Editor,QApplication,STYLE
from model import Document
app=QApplication([]);app.setApplicationName('IntervalSharedCanvasTests');app.setStyleSheet(STYLE)
QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc');app.setFont(QFont('Microsoft YaHei UI',10))
w=Editor(False);w.resize(1440,940);w.show();w.output.setVolume(0)
try:
    d=Document(bpm=120,audio=str(ROOT/'app/src/main/assets/desultory-signals.ogg'))
    d.regions[0].rects=[[.15,.1,.85,.6]]
    w.replace_document(d,None);w.seek(8);w.activateWindow();QTest.qWait(50)
    c=w.lanes.timeline;v=c.viewport()
    assert c.isVisible() and not w.stage.isVisible() and not w.agent_panel.isVisible()
    def point(col,beat):return QPoint(round(c.lane(col).center().x()),round(c.beat_y(beat)))
    def drag(col,a,b):
        QTest.mousePress(v,Qt.LeftButton,pos=point(col,a));QTest.mouseMove(v,point(col,b));QTest.mouseRelease(v,Qt.LeftButton,pos=point(col,b))
    def key(k):QTest.keyClick(c,k);app.processEvents()
    c.setFocus();key(Qt.Key_Q);QTest.mouseClick(v,Qt.LeftButton,pos=point(0,9))
    key(Qt.Key_R);drag(0,10,11);assert [(n.beat,n.length) for n in d.notes]==[(9,0),(10,1)]
    drag(1,8,9);assert d.lines[0].events['x'][0]['end']==9
    key(Qt.Key_E);assert w.lanes.region_mode and c.isVisible()
    drag(2,9,10);assert d.regions[0].events[0]['width'][0]['start']==9
    QTest.mouseClick(v,Qt.LeftButton,pos=point(2,9.5))
    panel=w.lanes.panel
    assert panel.fields.isVisible() and app.activeModalWidget() is None
    panel.values[1].setValue(0);QTest.mouseClick(panel.apply_button,Qt.LeftButton)
    assert d.regions[0].events[0]['width'][0]['to']==0
    f=QRectF(0,0,800,500);w.seek(6);static=w.timeline.region_background(f).boundingRect()
    w.seek(7);assert static==w.timeline.region_background(f).boundingRect()
    w.seek(11);assert w.timeline.region_background(f).isEmpty()
    assert abs(c.beat_y(10)-w.timeline.beat_y(10))<1
    w.undo();assert w.doc.regions[0].events[0]['width'][0]['to']==.7
    lanes=w.lanes;lanes.add_target();assert len(lanes.region.rects)==2 and lanes.index==1
    panel.name.setText('下半区');panel.rename();assert lanes.region.names[1]=='下半区'
    lanes.create_interval('center',12,14)
    for field,value in zip(panel.values,(50,500,50,-500)):field.setValue(value)
    panel.apply();assert lanes.region.events[1]['center'][0]['to']==[5,-5]
    lanes.remove_target();assert len(lanes.region.rects)==1
    panel.range_start.setValue(16);panel.range_end.setValue(20);panel.range_name.setText('过渡段')
    panel.apply_section();assert lanes.region.label=='过渡段' and w.cursor==16 and lanes.region.end==20
    w.undo();assert len(w.doc.regions)==1
    lanes.switch(False);lanes.add_target();count=len(w.doc.lines)
    lanes.create_interval('x',16,18)
    panel.values[0].setValue(-500);panel.values[1].setValue(500);panel.apply()
    assert (lanes.track.value('x',16),lanes.track.value('x',18))==(-5,5)
    panel.name.setText('旋律');panel.rename();assert lanes.track.name=='旋律'
    lanes.add_note(18);lanes.remove_target();assert len(w.doc.lines)==count
    lanes.delete_selected();lanes.remove_target();assert len(w.doc.lines)==count-1
    deadline=time.monotonic()+10
    while not w.hit_audio.mix_ready and time.monotonic()<deadline:QTest.qWait(10)
    w.activateWindow();QTest.qWait(25);c.setFocus();key(Qt.Key_T);dialog=w.preview_dialog;assert dialog and dialog.isVisible()
    QTest.qWait(350);assert w.playing()
    QTest.keyClick(dialog,Qt.Key_F11);QTest.qWait(50);assert dialog.isFullScreen()
    QTest.keyClick(dialog,Qt.Key_T);QTest.qWait(50);assert w.preview_dialog is None and not w.playing()
    w.open_inspector(2);assert w.agent_panel.isVisible();w.inspector.close();assert not w.agent_panel.isVisible()
    w.resize(1100,780);QTest.qWait(20)
    assert c.width()>=300 and w.timeline.width()>=400 and panel.width()>=208
    print('PASS: shared track/region gestures, Q/R/E, numeric edit, undo, stationary region and animated width, aligned grids, T playback, F11, return, Agent, compact layout')
finally:
    w.dirty=False;w.region_dirty=False;w.close()

