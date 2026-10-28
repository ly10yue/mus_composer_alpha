"""Slow typing and real spin-button clicks must survive timer-driven refreshes."""
import os,sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from main import QApplication,Editor,STYLE
from track_editor import TrackDialog
from PySide6.QtCore import QTimer,Qt
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtWidgets import QStyle,QStyleOptionSpinBox
from PySide6.QtTest import QTest
app=QApplication([]);app.setApplicationName('IntervalNumericTests');QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc');app.setFont(QFont('Microsoft YaHei UI',10));app.setStyleSheet(STYLE)
w=Editor(False);w.show();w.activateWindow();QTest.qWait(60);d=None
def type_number(box,text):
    box.setFocus();QTest.keyClick(box,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier);QTest.keyClicks(box,text,delay=80);QTest.qWait(120)
    assert box.lineEdit().text()==text,(text,box.lineEdit().text())
    QTest.keyClick(box,Qt.Key.Key_Return);QTest.qWait(40)
def up(box):
    option=QStyleOptionSpinBox();box.initStyleOption(option);rect=box.style().subControlRect(QStyle.ComplexControl.CC_SpinBox,option,QStyle.SubControl.SC_SpinBoxUp,box)
    assert not rect.isEmpty();before=box.value();step=box.singleStep();QTest.mouseClick(box,Qt.MouseButton.LeftButton,pos=rect.center());QTest.qWait(100)
    assert abs(box.value()-before-step)<1e-6,(box.value(),before,step)
try:
    timer=QTimer();timer.timeout.connect(w.update_position);timer.start(20)
    type_number(w.beat_jump,'12.375');assert abs(w.cursor-12.375)<1e-8;up(w.beat_jump)
    w.beat_jump.selectAll();QTest.keyClick(w.beat_jump,Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier)
    QApplication.clipboard().setText('14.625');QTest.keyClick(w.beat_jump,Qt.Key.Key_V,Qt.KeyboardModifier.ControlModifier);QTest.keyClick(w.beat_jump,Qt.Key.Key_Return);assert abs(w.cursor-14.625)<1e-8
    timer.stop();d=TrackDialog(w);d.show();d.activateWindow();QTest.qWait(70)
    type_number(d.preview_beat,'3.125');assert abs(w.cursor-3.125)<1e-8;up(d.preview_beat)
    d.create_interval('x',2,4);type_number(d.value_from,'37');up(d.value_from);d.write();assert abs(d.track.events['x'][0]['from']-.38)<1e-8
    print('PASS: slow typing, Ctrl+A/C/V, live refresh protection, exact paused seek, main/track time arrows and decimal value arrows')
finally:
    if d:d.reject()
    w.dirty=False;w.region_dirty=False;w.close()
