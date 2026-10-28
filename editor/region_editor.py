"""Four-lane rectangle authoring, sharing the line timeline and clipboard behavior."""
import copy
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut,QKeySequence
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QComboBox,QDialogButtonBox,QWidget,QScrollArea,QSplitter,QApplication,QLineEdit
from model import History,DIVISIONS
from region_events import RegionChannels,PROPS,LABELS,validate_channel,validate_region_events
from curves import EASES,EASE_NAMES
from track_editor import TrackDialog,number
from track_view import TrackTimeline
from numeric import sync_number
from views import Stage
from versioning import display_factor,APP_VERSION

class RegionDialog(TrackDialog):
    PROPS=PROPS
    LABELS=LABELS
    clipboard_kind='region'
    validate_channel=staticmethod(validate_channel)
    def __init__(self,editor,index=0,direct=True):
        QDialog.__init__(self,editor);self.editor=editor;self.doc=copy.deepcopy(editor.doc);self.history=History();self.index=index
        self.section_start=(self.doc.region_at(editor.cursor) or self.doc.regions[0]).start if direct else editor.area_start.value()
        if not direct:self.doc.set_region(self.section_start,editor.area_end.value(),editor.stage.rects,editor.area_label.text(),editor.stage.motions,editor.stage.events)
        self.index=max(0,min(index,len(self.region.rects)-1))
        self.selected=None;self.selection=set();self.tool='select';self.previous_window=editor.stage.window;editor.stage.window=self
        self.setWindowTitle('判定区域 · 0–100 坐标 · v'+APP_VERSION);self.setMinimumSize(1000,640)
        available=QApplication.primaryScreen().availableGeometry();self.resize(min(1450,available.width()-35),min(900,available.height()-55))
        outer=QVBoxLayout(self);top=QHBoxLayout();outer.addLayout(top)
        self.lines=QComboBox();self.lines.currentIndexChanged.connect(self.select_line);top.addWidget(self.lines)
        self.name=QLineEdit();self.name.editingFinished.connect(self.rename);top.addWidget(self.name,1)
        self.button('＋ 新建区域',self.add_line,top);self.button('删除区域',self.delete_line,top)
        self.undo_button=self.button('撤销',self.undo,top);self.redo_button=self.button('重做',self.redo,top)
        toolbar=QHBoxLayout();outer.addLayout(toolbar)
        self.grid_basis=QComboBox();self.grid_basis.addItems(['每拍','每小节']);self.grid_basis.setCurrentIndex(self.doc.grid_unit=='bar');self.grid_basis.currentIndexChanged.connect(self.grid_changed);toolbar.addWidget(self.grid_basis)
        self.division=QComboBox();self.division.addItems([f'1/{n}' for n in DIVISIONS]);self.division.setCurrentIndex(DIVISIONS.index(self.doc.division));self.division.currentIndexChanged.connect(self.grid_changed);toolbar.addWidget(self.division)
        toolbar.addWidget(QLabel('缩放'));self.zoom=number(max(.5,min(4,editor.scroll_factor)),4,.1);self.zoom.setMinimum(.5);self.zoom.valueChanged.connect(self.zoom_changed);toolbar.addWidget(self.zoom);toolbar.addStretch()
        sections=QHBoxLayout();outer.addLayout(sections);sections.addWidget(QLabel('生效段落'));self.sections=QComboBox();self.sections.currentIndexChanged.connect(self.select_section);sections.addWidget(self.sections,1)
        split=QSplitter();outer.addWidget(split,1);self.timeline=TrackTimeline(self);split.addWidget(self.timeline)
        panel=QWidget();right=QVBoxLayout(panel);self.selection_label=QLabel();self.selection_label.setWordWrap(True);right.addWidget(self.selection_label)
        form=QFormLayout();self.start=number(0,600000,self.doc.step);self.end=number(1,600000,self.doc.step)
        self.value_from=number();self.value_to=number();self.from_y=number();self.to_y=number()
        self.ease=QComboBox();self.ease.addItems(EASE_NAMES)
        for title,widget in [('起点 / 拍',self.start),('终点 / 拍',self.end),('起点值 / X',self.value_from),('终点值 / X',self.value_to),('起点 Y',self.from_y),('终点 Y',self.to_y),('变化类型',self.ease)]:form.addRow(title,widget)
        right.addLayout(form);row=QHBoxLayout();right.addLayout(row);self.write_button=self.button('应用选中长条',self.write,row);self.delete_button=self.button('删除',self.delete_selected,row)
        self.base_label=QLabel();self.base_label.setWordWrap(True);right.addWidget(self.base_label)
        help_text=QLabel('Ctrl＋拖动框选；Ctrl+C / V 复制粘贴；Delete 删除。\n滚轮每次一格；长/宽为旋转前的横/纵尺寸。\n仅在当前区域段落内显示和判定。');help_text.setWordWrap(True);help_text.setStyleSheet('color:#8da5a4;font-size:11px');right.addWidget(help_text)
        self.stage=Stage(self);self.stage.aspect=editor.stage.aspect;right.addWidget(self.stage,1);self.pose_label=QLabel();self.pose_label.setWordWrap(True);right.addWidget(self.pose_label)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);scroll.setWidget(panel);scroll.setMinimumWidth(300);scroll.setMaximumWidth(360);split.addWidget(scroll);split.setSizes([970,320])
        transport=QHBoxLayout();outer.addLayout(transport);self.play_button=self.button('▶ 播放 / 暂停',editor.toggle_play,transport)
        self.button('段落起点',lambda:editor.seek(self.section_start),transport);transport.addWidget(QLabel('预览拍'));self.preview_beat=number(editor.cursor,600000,self.doc.step);self.preview_beat.valueChanged.connect(editor.seek);transport.addWidget(self.preview_beat);transport.addStretch()
        self.hint=QLabel('新建区域默认：全屏（100 × 100），中心（50, 50），角度 0°。确定后整体应用，可撤销。');self.hint.setWordWrap(True);outer.addWidget(self.hint)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        for button in self.buttons.buttons():button.setAutoDefault(False)
        self.buttons.accepted.connect(self.accept);self.buttons.rejected.connect(self.reject);outer.addWidget(self.buttons)
        self.shortcuts=[]
        for key,fn in [('Ctrl+Z',self.undo),('Ctrl+Shift+Z',self.redo),('Ctrl+Y',self.redo)]:
            shortcut=QShortcut(QKeySequence(key),self);shortcut.activated.connect(fn);self.shortcuts.append(shortcut)
        editor.frameRendered.connect(self.tick);self.changed();self.select(None);self.zoom_changed();self.tick()
    @property
    def region(self):return self.doc.region_at(self.section_start)
    @property
    def track(self):
        r=self.region
        if not r.rects:return RegionChannels([0.,0.,1.,1.],[],{})
        if not r.events:r.events=[{} for _ in r.rects]
        return RegionChannels(r.rects[self.index],r.motions[self.index] if r.motions else [],r.events[self.index])
    def refresh_lines(self):
        self.lines.blockSignals(True);self.lines.clear()
        if not self.region.names:self.region.names=[f'区域 {i+1}' for i in range(len(self.region.rects))]
        for name in self.region.names:self.lines.addItem(name)
        if not self.name.hasFocus():self.name.setText(self.region.names[self.index] if self.region.rects else '')
        self.name.setEnabled(bool(self.region.rects))
        self.sections.blockSignals(True);self.sections.clear()
        for r in self.doc.regions:self.sections.addItem(f'{r.label} · {r.start:g} → {r.end:g} 拍',r.start)
        self.sections.setCurrentIndex(next(i for i,r in enumerate(self.doc.regions) if r.start==self.section_start));self.sections.blockSignals(False)
        self.lines.setCurrentIndex(self.index);self.lines.blockSignals(False)
        c=self.track.base('center');self.base_label.setText(f'初始中心 ({c[0]*100:g}, {c[1]*100:g}) · 角度 {self.track.base("angle"):g}°\n总长 {self.track.base("width")*100:g} · 总宽 {self.track.base("height")*100:g}')
    def select_line(self,index):
        if index<0:return
        self.pause();self.index=index;self.select(None);self.refresh_lines()
    def select_section(self,index):
        if index<0:return
        self.pause();self.section_start=self.sections.itemData(index);self.index=0
        if not self.region.rects:self.hint.setText('此段暂无区域；可点击新建区域。')
        self.changed();self.select(None);self.editor.seek(self.section_start)
    def rename(self):
        if not self.region.rects:return
        value=self.name.text().strip()[:80] or f'区域 {self.index+1}'
        if self.region.names[self.index]!=value:self.checkpoint();self.region.names[self.index]=value;self.changed()
    def add_line(self):
        if len(self.region.rects)>=32:self.hint.setText('每段最多 32 个区域');return
        self.name.clearFocus();self.checkpoint();r=self.region
        if not r.motions:r.motions=[[] for _ in r.rects]
        if not r.events:r.events=[{} for _ in r.rects]
        if not r.names:r.names=[f'区域 {i+1}' for i in range(len(r.rects))]
        r.rects.append([0.,0.,1.,1.]);r.motions.append([]);r.events.append({});r.names.append(f'区域 {len(r.rects)}');self.index=len(r.rects)-1;self.changed();self.select(None)
    def delete_line(self):
        if len(self.region.rects)<=1:self.hint.setText('至少保留一个区域');return
        self.checkpoint();r=self.region;r.rects.pop(self.index)
        for values in (r.motions,r.events,r.names):
            if values:values.pop(self.index)
        self.index=min(self.index,len(r.rects)-1);self.changed();self.select(None)
    def select(self,selected):
        self.selected=selected;self.selection={selected} if selected else set();item=self.selected_data();valid=item is not None
        for widget in (self.start,self.end,self.value_from,self.value_to,self.from_y,self.to_y,self.ease,self.write_button,self.delete_button):widget.setEnabled(valid)
        if valid:
            prop=selected[0];center=prop=='center';self.selection_label.setText(self.LABELS[self.PROPS.index(prop)])
            self.start.setValue(item['start']);self.end.setValue(item['end'])
            low,high=(-200,300) if center else (-36000,36000) if prop=='angle' else (.1,400)
            for box in (self.value_from,self.value_to,self.from_y,self.to_y):box.setRange(low,high);box.setSingleStep(5 if prop=='angle' else 1)
            self.value_from.setValue((item['from'][0] if center else item['from'])*display_factor(prop));self.value_to.setValue((item['to'][0] if center else item['to'])*display_factor(prop))
            self.from_y.setEnabled(center);self.to_y.setEnabled(center)
            if center:self.from_y.setValue(item['from'][1]*100);self.to_y.setValue(item['to'][1]*100)
            self.ease.setCurrentIndex(EASES.index(item.get('ease','linear')))
        else:self.selection_label.setText('在四栏拖出长条，设置起止值')
        self._inspector_state=self.inspector_values()
        self.timeline.viewport().update()
    def inspector_values(self):return super().inspector_values()+(self.from_y.value(),self.to_y.value())
    def store_event(self,prop,event,replace=None):
        if not self.region.rects:self.hint.setText('请先新建区域');return False
        items=copy.deepcopy(self.track.segments(prop))
        if replace is not None:items.pop(replace)
        items.append(event);items.sort(key=lambda e:e['start'])
        try:
            validate_channel(items,prop)
            if event['end']>self.doc.end_beat:raise ValueError('时间条超出谱面范围')
        except ValueError as ex:self.hint.setText(str(ex));return False
        self.checkpoint();self.track.events[prop]=items;self.changed();self.select((prop,items.index(event)));return True
    def edited_event(self):
        center=self.selected[0]=='center';factor=display_factor(self.selected[0])
        return dict(start=self.start.value(),end=self.end.value(),**{'from':[self.value_from.value()/100,self.from_y.value()/100] if center else self.value_from.value()/factor,'to':[self.value_to.value()/100,self.to_y.value()/100] if center else self.value_to.value()/factor},ease=EASES[self.ease.currentIndex()])
    def write(self):
        if self.selected_data() is not None:return self.store_event(self.selected[0],self.edited_event(),self.selected[1])
    def tick(self):
        sync_number(self.preview_beat,self.cursor);self.timeline.ensure_beat(self.cursor);self.stage.update()
        c=self.track.value('center',self.cursor);self.pose_label.setText(f'当前中心 ({c[0]*100:.3f}, {c[1]*100:.3f}) · {self.track.value("angle",self.cursor):.1f}°\n长 {self.track.value("width",self.cursor)*100:.3f} · 宽 {self.track.value("height",self.cursor)*100:.3f}')
    def undo(self):
        if self.history.undo_stack:self.pause();self.doc=self.history.undo(self.doc);self.index=max(0,min(self.index,len(self.region.rects)-1));self.changed();self.select(None)
    def redo(self):
        if self.history.redo_stack:self.pause();self.doc=self.history.redo(self.doc);self.index=max(0,min(self.index,len(self.region.rects)-1));self.changed();self.select(None)
    def accept(self):
        self.rename()
        if self.selected_data() is not None:
            for box in (self.start,self.end,self.value_from,self.value_to,self.from_y,self.to_y):box.interpretText()
            if self.inspector_values()!=getattr(self,'_inspector_state',None) and not self.write():return
        try:validate_region_events(self.region.events,len(self.region.rects))
        except ValueError as ex:self.hint.setText(str(ex));return
        QDialog.accept(self)
