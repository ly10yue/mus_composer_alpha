"""Real Qt panel + local HTTP provider. No paid model or user credential is used."""
import json,os,sys,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'editor'))
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtWidgets import QLineEdit,QDialogButtonBox
from PySide6.QtTest import QTest
from main import QApplication,Editor,STYLE
from model import Document,export_package
from agent_tools import fingerprint

ARGS=dict(region_index=0,rect_index=0,start_beat=4,end_beat=12,start_rect=[0,50,50,100],end_rect=[0,0,50,50],start_angle=0,end_angle=0,ease='linear')
def call(name,args,ident):return dict(choices=[dict(finish_reason='tool_calls',message=dict(role='assistant',content=None,tool_calls=[dict(id=ident,type='function',function=dict(name=name,arguments=json.dumps(args)))]))])
def answer(text):return dict(choices=[dict(finish_reason='stop',message=dict(role='assistant',content=text))])
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append(dict(path=self.path,body=body,authorization=self.headers.get('Authorization')))
        item=self.server.responses.pop(0) if self.server.responses else answer('完成')
        if isinstance(item,tuple):status,delay,data=item
        else:status,delay,data=200,0,item
        if delay:time.sleep(delay)
        data=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers()
        try:self.wfile.write(data)
        except OSError:pass

server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.requests=[];server.responses=[]
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
app=QApplication([]);app.setApplicationName('IntervalAgentTests');app.setStyleSheet(STYLE);QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc');app.setFont(QFont('Microsoft YaHei UI',10))
w=Editor(False);w.resize(1440,940);w.show();w.output.setVolume(0);p=w.agent_panel
song=str(ROOT/'app/src/main/assets/desultory-signals.ogg');screens=ROOT/'docs/screenshots/agent';screens.mkdir(parents=True,exist_ok=True)
def document():return Document(title='Agent editing test',bpm=120,duration=150.750667,audio=song)
def reset():
    w.replace_document(document(),None);w.load_region_draft(w.doc.regions[0]);w.stage.selected=0;w.tabs.setCurrentWidget(p);QTest.qWait(30)
def until(fn,timeout=6000):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if fn():return
        QTest.qWait(20)
    raise AssertionError('UI timeout: '+p.output.toPlainText()[-1500:])
try:
    reset();baseline=fingerprint(w.doc)
    # Prompt editing cannot trigger chart Q/R/V/Delete/Ctrl+A shortcuts.
    p.prompt.setFocus();QTest.keyClicks(p.prompt,'Q R V');assert p.prompt.toPlainText()=='Q R V'
    QTest.keyClick(p.prompt,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier);QTest.keyClick(p.prompt,Qt.Key.Key_Delete);assert not p.prompt.toPlainText() and not w.doc.notes
    QTest.mouseClick(p.demo_button,Qt.MouseButton.LeftButton);assert p.session and fingerprint(w.doc)==baseline
    w.seek(8);QTest.qWait(80);assert w.stage.window.doc is p.session.doc
    w.grab().save(str(screens/'local-draft.png'))
    QTest.mouseClick(p.apply_button,Qt.MouseButton.LeftButton);assert len(w.doc.regions)==3 and len(w.doc.region_at(8).motions[0])==2
    w.undo();assert fingerprint(w.doc)==baseline
    # Configure through the actual masked input UI; persisted JSON excludes key.
    failure=[]
    def configure():
        try:
            d=app.activeModalWidget();key=d.findChild(QLineEdit,'agentApiKey');assert key.echoMode()==QLineEdit.EchoMode.Password
            d.findChild(QLineEdit,'agentBaseUrl').setText(f'http://127.0.0.1:{server.server_port}/v1');d.findChild(QLineEdit,'agentModel').setText('local-fixture');key.setText('local-test-key')
            QTest.mouseClick(d.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save),Qt.MouseButton.LeftButton)
        except BaseException as ex:failure.append(ex);app.activeModalWidget().reject()
    QTimer.singleShot(150,configure);p.settings()
    if failure:raise failure[0]
    config=p.config_path.read_text(encoding='utf-8');assert 'local-test-key' not in config and 'api_key' not in config
    server.responses=[call('get_region',dict(region_index=0,rect_index=0),'read1'),call('animate_region',{**ARGS,'rect_index':99},'bad1'),call('animate_region',ARGS,'edit1'),call('validate_chart',{},'validate1'),answer('草稿：第二小节开头至第四小节开头（第 4–12 拍），左半屏自下向上匀速移动。')]
    p.prompt.setPlainText('这个判定区从第二小节到第四，在屏幕左半区由下方移至上方');QTest.mouseClick(p.send_button,Qt.MouseButton.LeftButton)
    assert p.client.active and not p.apply_button.isEnabled();until(lambda:not p.client.active)
    assert p.session and p.session.changed() and len(p.session.operations)==1 and fingerprint(w.doc)==baseline
    assert len(server.requests)==5 and all(r['path']=='/v1/chat/completions' for r in server.requests)
    assert all(r['authorization']=='Bearer local-test-key' for r in server.requests)
    payload=json.dumps(server.requests[-1]['body'],ensure_ascii=False)
    assert song not in payload and 'local-test-key' not in payload
    tools=[m for m in server.requests[-1]['body']['messages'] if m['role']=='tool'];assert any(not json.loads(m['content'])['ok'] for m in tools)
    # Follow-ups retain the draft and resolve the edited interval after a rounded seek.
    w.seek(3.999);server.responses=[call('animate_region',{**ARGS,'region_index':1,'ease':'smooth'},'refine'),answer('已将这段草稿改为平滑移动。')]
    p.prompt.setPlainText('把这个区改成平滑移动');p.send();until(lambda:not p.client.active)
    assert p.session and len(p.session.operations)==2 and p.session.doc.region_at(8).motions[0][0]['ease']=='smooth' and fingerprint(w.doc)==baseline
    preserved=fingerprint(p.session.doc);server.responses=[(401,0,dict(error='reflected local-test-key'))];p.prompt.setPlainText('继续调整');p.send();until(lambda:not p.client.active)
    assert p.session and fingerprint(p.session.doc)==preserved
    w.seek(8);QTest.qWait(50);w.grab().save(str(screens/'api-draft.png'));w.resize(1024,640);QTest.qWait(100);w.grab().save(str(screens/'small-window.png'));print('Small editor size:',w.width(),w.height());w.resize(1440,940);w.set_aspect(1);QTest.qWait(50);w.stage.grab().save(str(screens/'preview-4x3.png'))
    p.apply();assert len(w.doc.regions)==3;out=ROOT/'build/editor-tests/agent.interval';export_package(w.doc,out)
    assert 'local-test-key' not in json.dumps(w.doc.project()) and 'base_url' not in json.dumps(w.doc.project())
    w.undo();assert fingerprint(w.doc)==baseline
    # A concurrent manual edit is never overwritten by applying an older draft.
    p.demo();w.doc.title='Manual title';p.apply();assert w.doc.title=='Manual title' and len(w.doc.regions)==1;p.discard()
    reset();server.responses=[(401,0,dict(error='reflected local-test-key'))];p.prompt.setPlainText('移动');p.send();until(lambda:not p.client.active);assert p.session is None and 'local-test-key' not in p.output.toPlainText()
    reset();before=len(server.requests);server.responses=[(200,.4,call('animate_region',ARGS,'late'))];p.prompt.setPlainText('移动');p.send();until(lambda:len(server.requests)>before);p.cancel();QTest.qWait(500);assert p.session is None and len(w.doc.regions)==1
    reset();server.responses=[call('get_context',{},'loop')];p.config['max_rounds']=1;p.prompt.setPlainText('继续');p.send();until(lambda:not p.client.active);assert p.session is None and '轮数上限' in p.output.toPlainText();p.config['max_rounds']=8
    # Text-only clarification is a conversation, not a fabricated edit.
    reset();server.responses=[answer('请先选择要修改的矩形。')];p.prompt.setPlainText('这个区');p.send();until(lambda:not p.client.active);assert p.session is None and not p.apply_button.isEnabled()
    print('PASS: inline panel, masked API input, local demonstration, real HTTP tool loop, invalid call recovery, preview, apply/undo/export, stale draft protection, 401 redaction, cancel, round limit, clarification, no key/path persistence')
finally:
    p.client.cancel();p.config_path.unlink(missing_ok=True);w.dirty=False;w.region_dirty=False;w.close();server.shutdown();server.server_close()
