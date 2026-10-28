"""Open the shipped AT chart and inspect each authored scene through the real editor."""
import os,sys,time
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'editor'))
from main import QApplication,Editor,STYLE
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtTest import QTest
from model import export_package
app=QApplication([]);app.setApplicationName('IntervalATFlowTests');app.setStyleSheet(STYLE);QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc');app.setFont(QFont('Microsoft YaHei UI',10))
w=Editor(False);w.resize(1440,940);w.show();w.output.setVolume(0);w.hit_audio.bank.configure(False,0)
folder=ROOT/'docs/screenshots/at-flow';folder.mkdir(parents=True,exist_ok=True)
try:
    w.open_demo('at-flow.json');assert len(w.doc.notes)==711 and len(w.doc.lines)==10
    assert not w.doc.validate()[0]
    for beat,name in [(64,'traditional'),(128,'lift'),(196,'weave'),(248,'air'),(288,'garden'),(360,'return'),(396,'six-lines'),(448,'combined')]:
        w.seek(beat);QTest.qWait(60);w.grab().save(str(folder/(name+'.png')))
    w.set_aspect(1);w.seek(448);QTest.qWait(60);w.grab().save(str(folder/'combined-4x3.png'))
    w.resize(1024,640);QTest.qWait(80);assert w.width()==1024 and w.height()==640;w.grab().save(str(folder/'small-window.png'))
    package=ROOT/'build/editor-tests/at-flow-ui.interval';export_package(w.doc,package);original=w.doc.chart('music.ogg');w.open_path(package)
    assert w.doc.chart('music.ogg')==original
    print('PASS: shipped AT example, eight scenes, 4:3 and 16:9, small-window audio controls, full export/reimport')
finally:w.player.pause();w.dirty=False;w.region_dirty=False;w.close()
