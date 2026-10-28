"""Inline assistant tab. API work edits an isolated document until the user applies it."""
import copy
import json
import os
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QPlainTextEdit,
    QDialog,QFormLayout,QLineEdit,QSpinBox,QCheckBox,QDialogButtonBox,QScrollArea,QLayout)
from model import atomic_json
from agent_tools import EditSession,fingerprint
from agent_client import AgentClient,endpoint
from agent_config import default_api_key,load_agent_config,api_options

EXAMPLE='这个判定区从第二小节到第四，在屏幕左半区由下方移至上方'

class PreviewContext:
    agent_preview=True
    def __init__(self,panel):self.panel=panel
    @property
    def doc(self):return self.panel.session.doc if self.panel.session is not None else self.panel.editor.doc
    @property
    def cursor(self):return self.panel.editor.cursor
    def playing(self):return self.panel.editor.playing()

class AgentPanel(QWidget):
    def __init__(self,editor):
        super().__init__();self.editor=editor;self.session=None;self.previous=None;self.source_id=None;self.history=[];self.prompt_sent='';self._api_key=''
        self.config_path=editor.cache/'agent-config.json';self.config=load_agent_config(self.config_path)
        self.client=AgentClient(self);self.client.progress.connect(self.log);self.client.completed.connect(self.finished);self.client.failed.connect(self.failed)
        self.preview=PreviewContext(self)
        frame=QVBoxLayout(self);frame.setContentsMargins(0,0,0,0);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);frame.addWidget(scroll)
        content=QWidget();scroll.setWidget(content);outer=QVBoxLayout(content);outer.setContentsMargins(6,6,6,6);outer.setSpacing(5);outer.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        row=QHBoxLayout();outer.addLayout(row);self.settings_button=self.button('API 设置',self.settings,row);self.demo_button=self.button('无 Key 示例',self.demo,row);self.clear_button=self.button('清空对话',self.clear_chat,row)
        self.target_label=QLabel('');self.target_label.setWordWrap(True);self.target_label.setStyleSheet('color:#8da5a4;font-size:11px');outer.addWidget(self.target_label)
        self.prompt=QPlainTextEdit();self.prompt.setPlaceholderText(EXAMPLE+'\n先在“判定区域”中选中矩形，再输入指令。');self.prompt.setFixedHeight(76);outer.addWidget(self.prompt)
        row=QHBoxLayout();outer.addLayout(row);self.send_button=self.button('发送 / 生成草稿',self.send,row);self.send_button.setProperty('primary',True);self.cancel_button=self.button('停止请求',self.cancel,row);self.cancel_button.setEnabled(False)
        self.output=QPlainTextEdit();self.output.setReadOnly(True);self.output.setMinimumHeight(65);self.output.document().setMaximumBlockCount(1200);outer.addWidget(self.output,1)
        row=QHBoxLayout();frame.addLayout(row);self.preview_button=self.button('预览起点',self.preview_start,row);self.play_button=self.button('试听草稿',editor.toggle_play,row);self.apply_button=self.button('应用草稿',self.apply,row);self.apply_button.setProperty('primary',True);self.discard_button=self.button('丢弃',self.discard,row)
        self.hint=QLabel('上方预览草稿；应用后可 Ctrl+Z 撤销。Key 仅存本次内存。');self.hint.setWordWrap(True);self.hint.setStyleSheet('color:#8da5a4;font-size:11px');frame.addWidget(self.hint)
        self.log('Agent 就绪。配置支持工具调用的模型后发送；“无 Key 示例”仅演示固定的区域移动，不调用模型。');self.buttons()

    def button(self,text,fn,layout):
        b=QPushButton(text);b.clicked.connect(fn);layout.addWidget(b);return b
    def log(self,text):self.output.appendPlainText(str(text))

    def target(self,doc=None):
        d=doc or self.editor.doc;e=self.editor
        if doc is None:
            candidates=[(i,r) for i,r in enumerate(d.regions) if abs(r.start-e.area_start.value())<1e-5 and abs(r.end-e.area_end.value())<1e-5]
        else:candidates=[]
        anchor=e.cursor
        if doc is not None and self.session:
            # A follow-up's "this region" is the last edited interval, not the old
            # segment just before a millisecond-rounded audio seek boundary.
            for operation in reversed(self.session.operations):
                if operation['tool'] in ('animate_region','set_region'):
                    a=operation['arguments'];anchor=(a['start_beat']+a['end_beat'])/2;break
        if not candidates:candidates=[(i,r) for i,r in enumerate(d.regions) if r.start<=anchor<r.end]
        if not candidates:return None
        i,r=candidates[0];selected=e.stage.selected
        rect_index=selected if 0<=selected<len(r.rects) else (0 if len(r.rects)==1 else None)
        return dict(region_index=i,rect_index=rect_index,start_beat=r.start,end_beat=r.end,label=r.label,
                    rect=r.rects[rect_index] if rect_index is not None else None)

    def refresh_target(self):
        t=self.target(self.session.doc if self.session else None)
        self.target_label.setText(f'目标：段 {t["region_index"]+1} · 矩形 {t["rect_index"]+1 if t["rect_index"] is not None else "未选择"} · {t["start_beat"]:g}–{t["end_beat"]:g} 拍；小节从 1 开始。' if t else '当前没有可用区域，请先在“判定区域”中选择。')

    def buttons(self):
        busy=self.client.active;draft=self.session is not None and self.session.changed()
        self.send_button.setEnabled(not busy);self.demo_button.setEnabled(not busy);self.settings_button.setEnabled(not busy);self.clear_button.setEnabled(not busy);self.cancel_button.setEnabled(busy)
        self.apply_button.setEnabled(draft and not busy);self.discard_button.setEnabled(draft and not busy);self.preview_button.setEnabled(draft and not busy);self.play_button.setEnabled(draft and not busy)

    def settings(self):
        self.config=load_agent_config(self.config_path)
        dialog=QDialog(self);dialog.setWindowTitle('Agent API 设置');dialog.setMinimumWidth(520);layout=QFormLayout(dialog)
        base=QLineEdit(str(self.config['base_url']));model=QLineEdit(str(self.config['model']));model.setPlaceholderText('服务商提供的模型 ID，需要支持 tools / function calling')
        automatic_key=os.environ.get('INTERVAL_AGENT_API_KEY','') or default_api_key(self.config)
        key=QLineEdit(self._api_key or automatic_key);key.setEchoMode(QLineEdit.EchoMode.Password);key.setPlaceholderText('留空使用环境变量或已配置的本机 Bridge 密钥')
        def base_changed(value):
            # A prefilled local credential belongs only to its configured endpoint.
            if self._api_key:return
            try:same=endpoint(value)==endpoint(self.config['base_url'])
            except ValueError:same=False
            if not same and automatic_key and key.text()==automatic_key:key.clear()
            elif same and not key.text():key.setText(automatic_key)
        base.textChanged.connect(base_changed)
        base.setObjectName('agentBaseUrl');model.setObjectName('agentModel');key.setObjectName('agentApiKey')
        timeout=QSpinBox();timeout.setRange(5,120);timeout.setValue(int(self.config['timeout']));rounds=QSpinBox();rounds.setRange(1,12);rounds.setValue(int(self.config['max_rounds']))
        strict=QCheckBox('发送 strict schema（不兼容的服务可关闭）');strict.setChecked(bool(self.config['strict']))
        for title,w in [('Base URL',base),('模型 ID',model),('API Key',key),('每次请求超时 / 秒',timeout),('最多请求轮数',rounds),('',strict)]:layout.addRow(title,w)
        info=QLabel('协议：OpenAI 兼容 Chat Completions。自动追加 /chat/completions。\n仅在点击发送时联网；会发送指令、相关谱面数据和本面板对话。\n不会上传音频文件、本地路径或工程外文件。\n已配置的本机 Bridge 密钥自动填入，修改地址时清除自动填入值。\n设置仅保存密钥文件引用，手工输入的 Key 仅存内存。');info.setWordWrap(True);layout.addRow(info)
        error=QLabel('');error.setWordWrap(True);layout.addRow(error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);layout.addRow(buttons);buttons.rejected.connect(dialog.reject)
        def save():
            try:
                endpoint(base.text());config=dict(base_url=base.text().strip(),model=model.text().strip(),timeout=timeout.value(),max_rounds=rounds.value(),strict=strict.isChecked())
                for name in ('default_key_file','default_key_endpoint'):
                    if name in self.config:config[name]=self.config[name]
                atomic_json(self.config_path,config);self.config=config;entered=key.text().strip();self._api_key='' if entered==automatic_key else entered;dialog.accept()
            except (ValueError,OSError) as ex:error.setText(str(ex))
        buttons.accepted.connect(save);dialog.exec()

    def prepare(self):
        e=self.editor
        if e.region_dirty:raise ValueError('请先在“判定区域”中应用或放弃未提交的矩形草稿，再运行 Agent。')
        if self.session and (id(e.doc)!=self.source_id or fingerprint(e.doc)!=self.session.base_hash):raise ValueError('主谱面已改变，当前 Agent 草稿已过期。请丢弃后重新发送。')
        self.previous=self.session
        if self.session:
            self.session=copy.deepcopy(self.session);self.session.cursor=e.cursor;self.session.target=self.target(self.session.doc)
        else:self.session=EditSession(e.doc,e.selection,e.cursor,self.target());self.source_id=id(e.doc)
        e.player.pause();self.refresh_target()

    def send(self):
        prepared=False
        try:
            prompt=self.prompt.toPlainText().strip()
            if not prompt:raise ValueError('请输入制谱指令。')
            self.prepare();prepared=True;self.prompt_sent=prompt;self.log('\n你：'+prompt)
            key=self._api_key or os.environ.get('INTERVAL_AGENT_API_KEY','') or default_api_key(self.config)
            self.client.start(self.session,prompt,api_key=key,history=self.history,**api_options(self.config));self.buttons()
        except Exception as ex:
            if prepared:self.failed(str(ex))
            else:self.log('未发送：'+str(ex))

    def demo(self):
        prepared=False
        try:
            self.prepare();prepared=True;t=self.session.target
            if not t or t['rect_index'] is None:raise ValueError('请先选择一个具体矩形。')
            start=self.editor.doc.meter;end=3*self.editor.doc.meter
            if not t['start_beat']<=start<end<=t['end_beat']:raise ValueError('固定示例需选中覆盖第二小节开头至第四小节开头的段落；请使用新建工程演练。')
            l,top,r,b=t['rect'];width=min(.5,r-l);height=min(.5,b-top)
            args=dict(region_index=t['region_index'],rect_index=t['rect_index'],start_beat=start,end_beat=end,
                      start_rect=[0,(1-height)*100,width*100,100],end_rect=[0,0,width*100,height*100],start_angle=0,end_angle=0,ease='linear')
            self.session.call('animate_region',args);self.log('\n本地固定示例（未调用模型）：\n'+json.dumps(args,ensure_ascii=False,indent=2));self.present('第二小节开头 → 第四小节开头，在左半屏自下向上匀速移动。范围外保持原样。')
        except Exception as ex:
            if prepared:self.failed(str(ex))
            else:self.log('未演示：'+str(ex))

    def finished(self,text):
        self.history.extend([dict(role='user',content=self.prompt_sent),dict(role='assistant',content=text)]);self.history=self.history[-8:];self.prompt.clear();self.present(text)

    def present(self,text):
        self.previous=None;self.log('Agent：'+text)
        if self.session and self.session.changed():
            stats=self.session.summary();self.log(f'草稿包含 {stats["operations"]} 次编辑；区域段 {stats["regions_before"]} → {stats["regions_after"]}，音符 {stats["notes_before"]} → {stats["notes_after"]}，轨迹 {stats["lines_before"]} → {stats["lines_after"]}。')
            report=self.session.validation();self.log(f'谱面检查：{report["error_count"]} 个错误，{report["warning_count"]} 个提示。')
            if report['errors']:self.log('\n'.join(report['errors'][:8])+'\n可应用编辑草稿，导出前仍需修正上述问题。')
            self.preview_start()
        else:self.session=None;self.editor.stage.window=self.editor
        self.buttons();self.refresh_target()

    def failed(self,message):
        self.client.cancel();self.session=self.previous;self.previous=None;self.log('未应用：'+message);self.buttons();self.show_preview()

    def cancel(self):
        self.client.cancel();self.session=self.previous;self.previous=None;self.log('已停止请求，本次新增修改已丢弃。');self.buttons();self.show_preview()

    def show_preview(self):
        if self.editor.tabs.currentWidget() is self:
            self.editor.stage.window=self.preview if self.session and not self.client.active else self.editor
            self.editor.stage.editing=False;self.editor.stage.update()

    def preview_start(self):
        if self.session:self.editor.seek(self.session.preview_start);self.show_preview()

    def apply(self):
        if self.client.active or not self.session:return
        e=self.editor
        if id(e.doc)!=self.source_id or fingerprint(e.doc)!=self.session.base_hash or e.region_dirty:
            self.log('草稿过期：主谱面或区域草稿已改变。请丢弃并重新生成，避免覆盖手工修改。');return
        e.player.pause();e.checkpoint();e.doc=copy.deepcopy(self.session.doc);e.selection.intersection_update({n.id for n in e.doc.notes});self.session=None;self.previous=None;e.stage.window=e
        e.load_region_draft(e.doc.region_at(e.cursor) or e.doc.regions[0]);e.changed();self.log('已应用到主工程，可用 Ctrl+Z 一步撤销。保存和导出仍使用原有按钮。');self.history.append(dict(role='assistant',content='宿主状态：上一份草稿已应用到主工程。'));self.buttons();self.refresh_target()

    def discard(self):
        if self.client.active:self.cancel()
        self.session=None;self.previous=None;self.editor.stage.window=self.editor;self.editor.stage.update();self.log('已丢弃未应用草稿。');self.history.append(dict(role='assistant',content='宿主状态：上一份草稿已丢弃。'));self.buttons();self.refresh_target()

    def clear_chat(self):
        self.history=[];self.output.clear();self.log('对话已清空，谱面与当前草稿不变。')

    def reset_document(self):
        self.client.cancel();self.session=None;self.previous=None;self.source_id=None;self.history=[];self.editor.stage.window=self.editor;self.buttons()
