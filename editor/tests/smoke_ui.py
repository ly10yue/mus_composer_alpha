"""Exercise actual Qt widgets and mouse gestures; also produce review screenshots."""
import copy
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'editor'))
from PySide6.QtCore import Qt,QPoint,QPointF
from PySide6.QtGui import QFontDatabase,QFont,QWheelEvent
from PySide6.QtTest import QTest
from main import QApplication,Editor,STYLE
from model import Document,export_package,atomic_json

app=QApplication([]);app.setApplicationName('IntervalComposerTests');app.setStyleSheet(STYLE)
for font in ['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/consola.ttf','C:/Windows/Fonts/seguisym.ttf']:
    if Path(font).exists():QFontDatabase.addApplicationFont(font)
app.setFont(QFont('Microsoft YaHei UI',10))
w=Editor(False);w.resize(1440,940);w.show();w.output.setVolume(0);QTest.qWait(120)
w.scroll_speed.setValue(1.) # Keep the legacy gesture fixture's distant notes inside the viewport.
song=str(ROOT/'app/src/main/assets/desultory-signals.ogg')
w.replace_document(Document(title='Editor round trip',bpm=202,duration=150.750667,audio=song),None)
deadline=time.monotonic()+8
while (not w.audio_loaded or not w.hit_audio.mix_ready) and time.monotonic()<deadline:app.processEvents();time.sleep(.003)
assert w.audio_loaded,'real OGG loads'
QTest.qWait(100)
v=w.timeline.viewport()
def point(beat,x):return QPoint(round(w.timeline.x_at(x)),round(w.timeline.beat_y(beat)))
line=w.timeline.judgement_y()
assert abs(line-v.height()*.8)<.01 and w.timeline.beat_y(4)<w.timeline.beat_y(2)<line
# Header and pre-song space are not note placement targets.
w.set_tool('tap');QTest.mouseClick(v,Qt.MouseButton.LeftButton,pos=QPoint(250,10));QTest.mouseClick(v,Qt.MouseButton.LeftButton,pos=QPoint(250,round(line+30)));assert not w.doc.notes
w.set_tool('tap');w.division.setCurrentText('1/6');QTest.mouseClick(v,Qt.MouseButton.LeftButton,pos=point(2+.5,.18));assert abs(w.doc.notes[0].beat-2.5)<1e-6
w.set_tool('hold');QTest.mousePress(v,Qt.MouseButton.LeftButton,pos=point(4,.82));QTest.mouseMove(v,point(6,.82),20);QTest.mouseRelease(v,Qt.MouseButton.LeftButton,pos=point(6,.82));assert len(w.doc.notes)==2 and w.doc.notes[1].length==2
hold=w.doc.notes[1];assert w.timeline.note_rect(hold).contains(QPointF(w.timeline.x_at(.82),w.timeline.beat_y(5))) and w.timeline.beat_y(hold.beat+hold.length)<w.timeline.beat_y(hold.beat)
w.undo();assert len(w.doc.notes)==1;w.redo();assert len(w.doc.notes)==2
w.set_tool('select');QTest.mousePress(v,Qt.MouseButton.LeftButton,pos=point(6,.82));QTest.mouseMove(v,point(7,.82),20);QTest.mouseRelease(v,Qt.MouseButton.LeftButton,pos=point(7,.82));assert w.doc.notes[1].length==3;w.undo();assert w.doc.notes[1].length==2
QTest.mousePress(v,Qt.MouseButton.LeftButton,pos=point(2.5,.18));QTest.mouseMove(v,point(3.5,.39),20);QTest.mouseRelease(v,Qt.MouseButton.LeftButton,pos=point(3.5,.39));assert abs(w.doc.notes[0].beat-3.5)<1e-6 and w.doc.note_x(w.doc.notes[0])==.39;w.undo()
# Ruler, scrollbar and wheel all move time while the judgement line stays fixed.
QTest.mouseClick(v,Qt.MouseButton.LeftButton,pos=QPoint(40,round(w.timeline.beat_y(3))));assert abs(w.cursor-3)<.01 and w.timeline.judgement_y()==line
w.timeline.verticalScrollBar().setValue(4000);assert abs(w.cursor-4)<.01 and abs(w.timeline.beat_y(w.cursor)-line)<.01
def wheel(delta,modifiers=Qt.KeyboardModifier.NoModifier):
    event=QWheelEvent(QPointF(250,200),QPointF(v.mapToGlobal(QPoint(250,200))),QPoint(),QPoint(0,delta),Qt.MouseButton.NoButton,modifiers,Qt.ScrollPhase.NoScrollPhase,False)
    QApplication.sendEvent(v,event)
wheel(120);assert abs(w.cursor-(4+w.doc.step))<.01 and w.timeline.judgement_y()==line
cursor=w.cursor;wheel(120,Qt.KeyboardModifier.ControlModifier);assert w.cursor==cursor and w.timeline.ppb>64 and w.timeline.beat_y(cursor)==line
w.timeline.ppb=64;w.timeline.sync()
w.selection={w.doc.notes[0].id};w.copy_notes();w.seek(8);w.paste_notes();assert len(w.doc.notes)==3
w.mirror();assert abs(w.doc.note_x(w.doc.notes[-1])-.82)<1e-6
# A real drag on the region canvas, then commit an interval overlay.
w.tabs.setCurrentIndex(1);w.advanced_regions.setChecked(True);w.preset([]);w.stage.drawing=True
QTest.qWait(60);f=w.stage.field();start=QPoint(round(f.left()+f.width()*.05),round(f.top()+f.height()*.52));end=QPoint(round(f.left()+f.width()*.95),round(f.top()+f.height()*.95))
QTest.mousePress(w.stage,Qt.MouseButton.LeftButton,pos=start);QTest.mouseMove(w.stage,end,20);QTest.mouseRelease(w.stage,Qt.MouseButton.LeftButton,pos=end)
assert len(w.stage.rects)==1 and w.stage.rects[0][1]>.5
w.area_start.setValue(1);w.area_end.setValue(10);w.area_label.setText('下半区 / 编辑器导出');w.apply_region();assert w.doc.region_at(4).rects[0][1]>.5
# Region union and exact boundary serialization.
w.area_start.setValue(12);w.area_end.setValue(20);w.area_label.setText('双区');w.preset([[0,0,.46,1],[.54,0,1,1]]);w.apply_region();assert len(w.doc.region_at(12).rects)==2
assert not w.doc.validate()[0]
out=ROOT/'build/editor-tests';out.mkdir(parents=True,exist_ok=True)
export_package(w.doc,out/'roundtrip.interval');w.path=out/'roundtrip.ivproj';assert w.save();saved=w.doc.chart('music.ogg')
w.open_path(out/'roundtrip.interval');assert w.doc.chart('music.ogg')==saved
# Audio transport actually advances, then stops at pause; loop seeks back.
deadline=time.monotonic()+8
while (not w.audio_loaded or not w.hit_audio.mix_ready) and time.monotonic()<deadline:app.processEvents();time.sleep(.003)
w.seek(2);QTest.qWait(100);before=w.timeline.beat_y(4);w.toggle_play();QTest.qWait(450);assert w.playing() and w.cursor>2.3
assert w.timeline.beat_y(4)>before+20 and w.timeline.judgement_y()==line and abs(w.timeline.beat_y(w.cursor)-line)<.01,'notes and barlines fall while judgement line stays fixed'
w.toggle_play();frozen=w.player.position();QTest.qWait(160);assert abs(w.player.position()-frozen)<50
w.loop_a=2;w.loop_b=3;w.loop_check.setChecked(True);w.seek(2);w.toggle_play();QTest.qWait(1200);assert 1.8<=w.cursor<=3.3;w.toggle_play();w.loop_check.setChecked(False)
w.autosave();w.doc.title='Native desktop composer';w.changed();w.autosave();assert w.recovery_path.exists()
screens=ROOT/'docs/screenshots/editor';screens.mkdir(parents=True,exist_ok=True)
w.open_path(ROOT/'app/src/main/assets/demo.json');w.seek(34);QTest.qWait(120);w.tabs.setCurrentIndex(0);w.grab().save(str(screens/'notes.png'))
w.tabs.setCurrentIndex(1);w.select_region(w.region_list.topLevelItem(1),0);QTest.qWait(120);w.grab().save(str(screens/'regions.png'))
w.resize(1100,780);QTest.qWait(120);w.grab().save(str(screens/'compact.png'))
scroll=w.tabs.widget(1);scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum());QTest.qWait(100);w.grab().save(str(screens/'compact-properties.png'))
w.dirty=False;w.region_dirty=False;w.close()
print('PASS: fixed judgement line, falling notes/grid, ruler/scrollbar/wheel seeking, zoom, 1/6 snap, Tap/Hold/move/tail gestures, undo/redo, copy/paste, mirror, regions, export/reimport, save, real OGG playback, pause, loop, autosave, desktop layouts')
