"""Four-lane track authoring with a cancellable document draft."""
import copy
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut,QKeySequence
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,QComboBox,
    QPushButton,QDialogButtonBox,QWidget,QScrollArea,QSplitter,QApplication)
from model import History,DIVISIONS
from tracks import Track,validate_tracks
from curves import EASES,EASE_NAMES,validate_events
from numeric import NumberBox,sync_number
from views import Stage
from track_view import TrackTimeline
from timeline_edit import BatchTimelineEdits
from versioning import display_factor,APP_VERSION

PROPS=('notes','x','alpha','speed')
LABELS=('绑定音符','横向位置','线透明度','音符流速')

def number(value=0,maximum=600000,step=.25):
    w=NumberBox();w.setDecimals(4);w.setRange(0,maximum);w.setSingleStep(step);w.setValue(value);return w

class TrackDialog(BatchTimelineEdits,QDialog):
    PROPS=PROPS
    LABELS=LABELS
    validate_channel=staticmethod(validate_events)
    def __init__(self,editor):
        super().__init__(editor);self.editor=editor;self.doc=copy.deepcopy(editor.doc);self.history=History()
        self.index=max(0,next((i for i,t in enumerate(self.doc.lines) if t.id==editor.line_combo.currentData()),0))
        self.selected=None;self.selection=set();self.tool='select';self.previous_window=editor.stage.window;editor.stage.window=self
        self.setWindowTitle('轨迹编辑 · 0–100 坐标 · v'+APP_VERSION);self.setMinimumSize(1000,640)
        available=QApplication.primaryScreen().availableGeometry();self.resize(min(1450,available.width()-35),min(900,available.height()-55))
        outer=QVBoxLayout(self);top=QHBoxLayout();outer.addLayout(top)
        self.lines=QComboBox();self.lines.setMinimumWidth(160);self.lines.currentIndexChanged.connect(self.select_line);top.addWidget(self.lines)
        self.name=QLineEdit();self.name.setPlaceholderText('轨迹名称');self.name.editingFinished.connect(self.rename);top.addWidget(self.name,1)
        self.button('＋ 新建线',self.add_line,top);self.button('删除线',self.delete_line,top)
        self.undo_button=self.button('撤销',self.undo,top);self.redo_button=self.button('重做',self.redo,top)
        toolbar=QHBoxLayout();outer.addLayout(toolbar);self.tools={}
        for kind,label in [('select','选择 / 拖动'),('tap','Tap'),('hold','Hold')]:
            button=self.button(label,lambda checked=False,k=kind:self.set_tool(k),toolbar);button.setCheckable(True);self.tools[kind]=button
        toolbar.addSpacing(12);self.grid_basis=QComboBox();self.grid_basis.addItems(['每拍','每小节']);self.grid_basis.setCurrentIndex(self.doc.grid_unit=='bar');self.grid_basis.currentIndexChanged.connect(self.grid_changed);toolbar.addWidget(self.grid_basis)
        self.division=QComboBox();self.division.addItems([f'1/{n}' for n in DIVISIONS]);self.division.setCurrentIndex(DIVISIONS.index(self.doc.division));self.division.currentIndexChanged.connect(self.grid_changed);toolbar.addWidget(self.division)
        toolbar.addWidget(QLabel('缩放'));self.zoom=number(max(.5,min(4,editor.scroll_factor)),4,.1);self.zoom.setMinimum(.5);self.zoom.setSuffix('×');self.zoom.valueChanged.connect(self.zoom_changed);toolbar.addWidget(self.zoom);toolbar.addStretch()
        split=QSplitter();outer.addWidget(split,1);self.timeline=TrackTimeline(self);split.addWidget(self.timeline)
        panel=QWidget();right=QVBoxLayout(panel);right.setContentsMargins(8,2,8,2)
        self.selection_label=QLabel('在后三栏拖出长条，设置起止值');self.selection_label.setWordWrap(True);self.selection_label.setStyleSheet('color:#a6f4cf;font-weight:600');right.addWidget(self.selection_label)
        form=QFormLayout();self.start=number(0,600000,self.doc.step);self.end=number(1,600000,self.doc.step)
        self.value_from=number(.5,1,.01);self.value_to=number(.5,1,.01);self.ease=QComboBox();self.ease.addItems(EASE_NAMES)
        for title,widget in [('起点 / 拍',self.start),('终点 / 拍',self.end),('起点值',self.value_from),('终点值',self.value_to),('变化类型',self.ease)]:form.addRow(title,widget)
        right.addLayout(form);row=QHBoxLayout();right.addLayout(row)
        self.write_button=self.button('应用选中长条',self.write,row);self.delete_button=self.button('删除',self.delete_selected,row)
        self.base_label=QLabel();self.base_label.setWordWrap(True);right.addWidget(self.base_label)
        help_text=QLabel('第 1 栏：放置 Tap，或拖出 Hold；音符自动绑定当前线。\n第 2–4 栏：拖出时间长条，右侧填写起止值和变化类型。\n选择后拖动中部移动时间，拖两端改变范围；右键删除。\n区间之间保持上一段终值。同一栏不允许重叠。\nCtrl＋拖动框选；Ctrl+C / V 复制粘贴；Delete 批量删除。\n滚轮每次一格；Ctrl＋滚轮缩放。')
        help_text.setWordWrap(True);help_text.setStyleSheet('color:#8da5a4;font-size:11px');right.addWidget(help_text)
        self.stage=Stage(self);self.stage.aspect=editor.stage.aspect;self.stage.setMinimumHeight(190);right.addWidget(self.stage,1)
        self.pose_label=QLabel();self.pose_label.setWordWrap(True);right.addWidget(self.pose_label)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);scroll.setWidget(panel);scroll.setMinimumWidth(300);scroll.setMaximumWidth(360);split.addWidget(scroll);split.setSizes([970,320])
        transport=QHBoxLayout();outer.addLayout(transport);self.play_button=self.button('▶ 播放 / 暂停',editor.toggle_play,transport)
        self.button('回到开头',lambda:editor.seek(0),transport);transport.addWidget(QLabel('预览拍'));self.preview_beat=number(editor.cursor,600000,self.doc.step);self.preview_beat.valueChanged.connect(editor.seek);transport.addWidget(self.preview_beat)
        self.button('定位选中起点',lambda:editor.seek(self.start.value()),transport);transport.addStretch()
        self.hint=QLabel('新建线默认：无音符 · 位置 50 · 透明度 0 · 流速 1×。确定后可整体撤销。');self.hint.setWordWrap(True);outer.addWidget(self.hint)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        for button in self.buttons.buttons():button.setAutoDefault(False)
        self.buttons.accepted.connect(self.accept);self.buttons.rejected.connect(self.reject);outer.addWidget(self.buttons)
        self.shortcuts=[]
        for key,fn in [('Ctrl+Z',self.undo),('Ctrl+Shift+Z',self.redo),('Ctrl+Y',self.redo)]:
            shortcut=QShortcut(QKeySequence(key),self);shortcut.activated.connect(fn);self.shortcuts.append(shortcut)
        editor.frameRendered.connect(self.tick)
        self.refresh_lines();self.select(None);self.set_tool('select');self.zoom_changed();self.tick()
    @property
    def cursor(self):return self.editor.cursor
    @property
    def track(self):return self.doc.lines[self.index]
    def playing(self):return self.editor.playing()
    def pause(self):self.editor.hit_audio.pause()
    def button(self,label,fn,layout):
        b=QPushButton(label);b.setAutoDefault(False);b.clicked.connect(fn);layout.addWidget(b);return b
    def checkpoint(self):self.pause();self.history.push(self.doc)
    def changed(self):
        self.refresh_lines();self.timeline.sync();self.stage.update();self.editor.hit_audio.invalidate()
        self.grid_basis.blockSignals(True);self.grid_basis.setCurrentIndex(self.doc.grid_unit=='bar');self.grid_basis.blockSignals(False)
        self.division.blockSignals(True);self.division.setCurrentIndex(DIVISIONS.index(self.doc.division));self.division.blockSignals(False)
        for box in (self.start,self.end,self.preview_beat):box.setSingleStep(self.doc.step)
        self.undo_button.setEnabled(bool(self.history.undo_stack));self.redo_button.setEnabled(bool(self.history.redo_stack))
    def refresh_lines(self):
        self.lines.blockSignals(True);self.lines.clear()
        for t in self.doc.lines:self.lines.addItem(f'{t.name} · {sum(n.line==t.id for n in self.doc.notes)} 音符',t.id)
        self.lines.setCurrentIndex(self.index);self.lines.blockSignals(False)
        if not self.name.hasFocus():self.name.setText(self.track.name)
        self.base_label.setText(f'初始值：位置 {self.track.base("x")*100:g} · 透明度 {self.track.base("alpha"):g} · 流速 1×')
    def select_line(self,index):
        if index<0:return
        self.pause();self.index=index;self.selected=None;self.name.setText(self.track.name);self.refresh_lines();self.select(None);self.timeline.viewport().update()
    def rename(self):
        name=self.name.text().strip() or self.track.id
        if name!=self.track.name:self.checkpoint();self.track.name=name;self.changed()
    def add_line(self):
        if len(self.doc.lines)>=64:self.hint.setText('最多支持 64 条轨迹。');return
        self.name.clearFocus()
        self.checkpoint();ident=self.doc.new_line_id();self.doc.lines.append(Track(ident,'轨迹 '+ident[4:],[dict(beat=0.,x=.5,alpha=0.,ease='linear')]))
        self.index=len(self.doc.lines)-1;self.name.clearFocus();self.changed();self.select(None)
    def delete_line(self):
        if len(self.doc.lines)==1:self.hint.setText('至少保留一条轨迹。');return
        if any(n.line==self.track.id for n in self.doc.notes):self.hint.setText('这条轨迹仍有音符；请先删除或改绑音符。');return
        self.checkpoint();self.doc.lines.pop(self.index);self.index=min(self.index,len(self.doc.lines)-1);self.changed();self.select(None)
    def grid_changed(self):
        if not hasattr(self,'timeline'):return
        self.doc.grid_unit='bar' if self.grid_basis.currentIndex() else 'beat';self.doc.division=DIVISIONS[self.division.currentIndex()]
        for box in (self.start,self.end,self.preview_beat):box.setSingleStep(self.doc.step)
        self.timeline.sync()
    def zoom_changed(self):
        if hasattr(self,'timeline'):self.timeline.ppb=64*self.zoom.value();self.timeline.sync()
    def set_tool(self,kind):
        self.tool=kind
        for name,button in self.tools.items():button.setChecked(name==kind)
    def tick(self):
        sync_number(self.preview_beat,self.cursor);self.timeline.ensure_beat(self.cursor);self.stage.update()
        self.pose_label.setText(f'当前：位置 {self.track.value("x",self.cursor)*100:.3f} · 透明度 {self.track.value("alpha",self.cursor):.3f} · 流速 {self.track.value("speed",self.cursor):.3f}×')
    def selected_data(self):
        if not self.selected:return None
        prop,index=self.selected
        if prop=='notes':return next((n for n in self.doc.notes if n.id==index and n.line==self.track.id),None)
        items=self.track.segments(prop);return items[index] if index<len(items) else None
    def select(self,selected):
        self.selected=selected;self.selection={selected} if selected else set();item=self.selected_data();valid=item is not None
        for widget in (self.start,self.end,self.value_from,self.value_to,self.ease,self.write_button,self.delete_button):widget.setEnabled(valid)
        if not valid:self.selection_label.setText('在后三栏拖出长条，设置起止值');self.timeline.viewport().update();return
        prop,index=selected;self.selection_label.setText(self.LABELS[self.PROPS.index(prop)]+(' · Tap' if prop=='notes' and not item.length else ' · Hold' if prop=='notes' else ' · 区间'))
        self.start.setValue(item.beat if prop=='notes' else item['start']);self.end.setValue(item.beat+item.length if prop=='notes' else item['end'])
        for widget in (self.value_from,self.value_to,self.ease):widget.setEnabled(prop!='notes')
        if prop!='notes':
            for widget in (self.value_from,self.value_to):widget.setMaximum(8 if prop=='speed' else 100 if prop=='x' else 1);widget.setSingleStep(.1 if prop=='speed' else 1 if prop=='x' else .01)
            self.value_from.setValue(item['from']*display_factor(prop));self.value_to.setValue(item['to']*display_factor(prop));self.ease.setCurrentIndex(EASES.index(item.get('ease','linear')))
        self._inspector_state=self.inspector_values()
        self.timeline.viewport().update()
    def inspector_values(self):return (self.start.value(),self.end.value(),self.value_from.value(),self.value_to.value(),self.ease.currentIndex())
    def store_event(self,prop,event,replace=None):
        items=copy.deepcopy(self.track.segments(prop))
        if replace is not None:items.pop(replace)
        items.append(event);items.sort(key=lambda e:e['start'])
        try:validate_events(items,prop)
        except ValueError as ex:self.hint.setText(str(ex));return False
        self.checkpoint();self.track.events[prop]=items;self.track.invalidate();self.changed();self.select((prop,items.index(event)));self.hint.setText('已写入草稿；长条内标出起止值与变化类型。');return True
    def create_interval(self,prop,start,end):
        start,end=sorted((start,end));end=max(end,start+self.doc.step);end=min(end,self.doc.end_beat)
        return self.store_event(prop,dict(start=start,end=end,**{'from':self.track.value(prop,start),'to':self.track.value(prop,end)},ease='linear'))
    def add_note(self,start,end=None):
        if end is not None:start,end=sorted((start,end))
        if start<0 or start>self.doc.end_beat:return
        if any(n.line==self.track.id and abs(n.beat-start)<1e-7 for n in self.doc.notes):self.hint.setText('同一条线在这一拍已有音符。');return
        self.checkpoint();note=self.doc.add(start,self.track.id,0 if end is None else max(self.doc.step,end-start));self.changed();self.select(('notes',note.id))
    def update_note(self,note,start,end):
        if not 0<=start<=end<=self.doc.end_beat or any(n.id!=note.id and n.line==note.line and abs(n.beat-start)<1e-7 for n in self.doc.notes):self.hint.setText('音符时间超出范围或与同线音符重叠。');return False
        self.checkpoint();note.beat=start;note.length=end-start;self.changed();self.select(('notes',note.id));return True
    def write(self):
        item=self.selected_data()
        if item is None:return
        prop,index=self.selected
        if prop=='notes':self.update_note(item,self.start.value(),self.end.value());return
        self.store_event(prop,dict(start=self.start.value(),end=self.end.value(),**{'from':self.value_from.value()/display_factor(prop),'to':self.value_to.value()/display_factor(prop)},ease=EASES[self.ease.currentIndex()]),index)
    def delete_single_legacy(self):
        if self.selected_data() is None:return
        prop,index=self.selected;self.checkpoint()
        if prop=='notes':self.doc.notes=[n for n in self.doc.notes if n.id!=index]
        else:
            items=copy.deepcopy(self.track.segments(prop));items.pop(index);self.track.events[prop]=items;self.track.invalidate()
        self.changed();self.select(None)
    def undo(self):
        if not self.history.undo_stack:return
        self.pause();self.doc=self.history.undo(self.doc);self.index=min(self.index,len(self.doc.lines)-1);self.changed();self.select(None)
    def redo(self):
        if not self.history.redo_stack:return
        self.pause();self.doc=self.history.redo(self.doc);self.index=min(self.index,len(self.doc.lines)-1);self.changed();self.select(None)
    def accept(self):
        self.rename()
        try:validate_tracks(self.doc.lines)
        except ValueError as ex:self.hint.setText(str(ex));return
        if self.selected_data() is not None:
            for widget in (self.start,self.end,self.value_from,self.value_to):widget.interpretText()
            if self.inspector_values()==getattr(self,'_inspector_state',None):super().accept();return
            if self.selected[0]!='notes':
                prop,index=self.selected;event=dict(start=self.start.value(),end=self.end.value(),**{'from':self.value_from.value()/display_factor(prop),'to':self.value_to.value()/display_factor(prop)},ease=EASES[self.ease.currentIndex()])
                if event!=self.selected_data() and not self.store_event(prop,event,index):return
            elif (self.start.value(),self.end.value())!=(self.selected_data().beat,self.selected_data().beat+self.selected_data().length):
                if not self.update_note(self.selected_data(),self.start.value(),self.end.value()):return
        super().accept()
    def done(self,result):
        self.editor.frameRendered.disconnect(self.tick);self.pause();self.editor.stage.window=self.previous_window;self.editor.hit_audio.invalidate();super().done(result)
