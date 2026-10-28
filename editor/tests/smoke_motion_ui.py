"""Motion dialog -> apply -> undo -> save/export -> preview, using real Qt widgets."""
import copy,json,os,sys,time
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'editor'))
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtTest import QTest
from main import QApplication,Editor,STYLE
from region_editor import RegionDialog
from model import Document,export_package,atomic_json
from motion import polygon,touch_y,ASPECTS

app=QApplication([]);app.setApplicationName('IntervalMotionTests');app.setStyleSheet(STYLE)
for file in ('msyh.ttc','consola.ttf'):
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+file)
app.setFont(QFont('Microsoft YaHei UI',10))
w=Editor(False);w.resize(1440,940);w.show();w.output.setVolume(0)
doc=Document(title='Moving regions / UI round trip',bpm=120,duration=150.750667,audio=str(ROOT/'app/src/main/assets/desultory-signals.ogg'))
doc.add(2,.5);doc.add(4,.5,2);doc.add(8,.5)
w.replace_document(doc,None);w.tabs.setCurrentIndex(1);w.preset([[.15,.3,.85,.65]]);w.area_start.setValue(0);w.area_end.setValue(20);w.stage.selected=0;w.rect_selected();QTest.qWait(100)
screens=ROOT/'docs/screenshots/motion';screens.mkdir(parents=True,exist_ok=True)
failure=[]
w.stage.motions=[[dict(beat=0,x=0,y=0,angle=0,ease="smooth"),dict(beat=8,x=.05,y=.15,angle=45,ease="linear")]]
def edit_dialog():
    try:
        d=app.activeModalWidget();assert isinstance(d,RegionDialog)
        assert len(d.track.segments('center'))==1 and len(d.track.segments('angle'))==1
        d.select(('angle',0));d.value_to.setValue(45);d.ease.setCurrentIndex(4);QTest.mouseClick(d.write_button,Qt.MouseButton.LeftButton)
        assert d.track.events['angle'][0]['to']==45
        w.seek(4);QTest.qWait(100);d.grab().save(str(screens/'keyframes.png'))
        d.create_interval('width',9,10);assert len(d.track.events['width'])==1;d.delete_selected();assert not d.track.events['width']
        assert not any(w.doc.regions[0].motions)
        d.accept()
    except BaseException as ex:
        failure.append(ex);app.activeModalWidget().reject()
QTimer.singleShot(100,edit_dialog);w.edit_motion()
if failure:raise failure[0]
assert w.region_dirty and w.stage.motions[0][1]['angle']==45 and w.motion_preview.isChecked()
w.autosave();recovery=json.loads(w.recovery_path.read_text(encoding='utf-8'));assert recovery['areaDraft']['motions'][0][1]['angle']==45
w.apply_region();assert w.doc.regions[0].motions[0][1]['angle']==45
w.undo();assert not any(w.doc.regions[0].motions);w.redo();assert w.doc.regions[0].motions[0][1]['angle']==45
w.load_region_draft(w.doc.regions[0]);w.stage.selected=0;w.rect_selected();before=copy.deepcopy(w.stage.motions)
def cancel_dialog():
    d=app.activeModalWidget();d.track.events.clear();d.reject()
QTimer.singleShot(80,cancel_dialog);w.edit_motion();assert w.stage.motions==before
w.seek(4);QTest.qWait(100);w.grab().save(str(screens/'editor-16x9.png'));w.set_aspect(1);QTest.qWait(100);w.grab().save(str(screens/'editor-4x3.png'))
out=ROOT/'build/editor-tests';out.mkdir(parents=True,exist_ok=True)
w.path=out/'motion.ivproj';assert w.save();export_package(w.doc,out/'motion.interval');chart=w.doc.chart('music.ogg');assert chart['version']==6
region=w.doc.regions[0];samples=[]
for aspect in ASPECTS:
    for beat in [0,.5,1,2,3,4,5,6,7,8,10,14,18]:
        samples.append(dict(time=w.doc.seconds(beat),aspect=aspect,polygon=[v for pt in polygon(region.rects[0],region.motions[0],beat,aspect,region.events[0]) for v in pt],touches=[dict(x=x,y=touch_y(region.rects[0],region.motions[0],beat,aspect,x,region.events[0])) for x in [0,.1,.18,.39,.5,.61,.82,.9,1]]))
atomic_json(out/'motion-parity.json',samples)
w.open_path(out/'motion.interval');assert w.doc.chart('music.ogg')==chart
deadline=time.monotonic()+5
while (not w.audio_loaded or not w.hit_audio.mix_ready) and time.monotonic()<deadline:app.processEvents();time.sleep(.003)
w.tabs.setCurrentIndex(0);w.seek(2);shape=polygon(w.doc.regions[0].rects[0],w.doc.regions[0].motions[0],w.cursor,1.6);w.toggle_play();QTest.qWait(500);w.toggle_play()
assert w.cursor>2.5 and polygon(w.doc.regions[0].rects[0],w.doc.regions[0].motions[0],w.cursor,1.6)!=shape
w.dirty=False;w.region_dirty=False;w.close()
print('PASS: legacy motion import and four-lane controls, add/update/delete, cancel, live preview, apply, undo/redo, autosave, v5 project/package round trip, both aspect previews, real playback')
