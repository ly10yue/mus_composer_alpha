"""Persistent object and event properties beside the shared four-lane timeline."""
from PySide6.QtCore import Qt,QPointF,QRectF
from PySide6.QtGui import QColor,QPainter,QPen,QPolygonF
from PySide6.QtWidgets import (QWidget,QScrollArea,QVBoxLayout,QHBoxLayout,QFormLayout,
    QLabel,QComboBox,QLineEdit,QPushButton,QFrame)
from curves import EASES,EASE_NAMES,eased
from track_editor import number
from versioning import display_range,display_factor


class CurvePreview(QWidget):
    def __init__(self):
        super().__init__();self.setFixedHeight(70);self.values=[];self.ease='linear'
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        area=QRectF(self.rect()).adjusted(6,6,-6,-6);p.fillRect(area,QColor('#10191b'))
        p.setPen(QPen(QColor('#304244'),1));p.drawRect(area)
        if not self.values:return
        low=min(min(pair) for pair in self.values);high=max(max(pair) for pair in self.values)
        for (a,b),color in zip(self.values,('#a6f4cf','#83c9f4')):
            def point(t,u):
                v=a+(b-a)*u
                return QPointF(area.left()+area.width()*t,area.center().y() if low==high else area.bottom()-(v-low)/(high-low)*area.height())
            samples=([point(0,0),point(1,0),point(1,1)] if self.ease=='hold' else
                     [point(i/48,eased(i/48,self.ease)) for i in range(49)])
            p.setPen(QPen(QColor(color),2));p.drawPolyline(QPolygonF(samples))


class LaneInspector(QScrollArea):
    def __init__(self,lanes):
        super().__init__();self.lanes=lanes;self.loading=False
        self.setWidgetResizable(True);self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumWidth(208);self.setMaximumWidth(360);self.setFrameShape(QFrame.Shape.NoFrame)
        panel=QWidget();self.setWidget(panel);box=QVBoxLayout(panel);box.setContentsMargins(8,3,5,4);box.setSpacing(6)
        self.title=QLabel('四栏编辑');box.addWidget(self.title)
        def row(layout):
            r=QHBoxLayout();r.setSpacing(4);layout.addLayout(r);return r
        def button(layout,label,fn):
            b=QPushButton(label);b.clicked.connect(fn);layout.addWidget(b);return b
        modes=row(box);lanes.editor.mode_buttons=[]
        for i,label in enumerate(('轨道','区域')):
            b=button(modes,label,lambda checked=False,i=i:lanes.switch(bool(i)))
            b.setCheckable(True);b.setToolTip('E 切换轨道 / 区域');lanes.editor.mode_buttons.append(b)
        lanes.editor.mode_buttons[0].setChecked(True)
        self.sections=QComboBox();self.sections.setToolTip('跳到生效段落');box.addWidget(self.sections)
        self.sections.activated.connect(lambda i:lanes.editor.seek(self.sections.itemData(i)))
        box.addWidget(lanes.targets);lanes.targets.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.name=QLineEdit();self.name.setMaxLength(80);self.name.setPlaceholderText('对象名称')
        names=row(box);names.addWidget(self.name,1);button(names,'改名',self.rename);self.name.returnPressed.connect(self.rename)
        actions=row(box);button(actions,'新建',lanes.add_target);self.remove=button(actions,'删除对象',lanes.remove_target)
        self.segment=QPushButton('分段');actions.addWidget(self.segment);self.segment.setCheckable(True)
        self.range_box=QWidget();bounds=QFormLayout(self.range_box);bounds.setContentsMargins(0,0,0,0)
        self.range_start=number();self.range_end=number();self.range_name=QLineEdit()
        for label,w in [('段落名',self.range_name),('从拍',self.range_start),('到拍',self.range_end)]:bounds.addRow(label,w)
        range_actions=QHBoxLayout();button(range_actions,'覆盖此段',self.apply_section);button(range_actions,'矩形画布…',self.open_rectangles)
        bounds.addRow(range_actions);box.addWidget(self.range_box);self.range_box.hide();self.segment.toggled.connect(self.range_box.setVisible)
        line=QFrame();line.setFrameShape(QFrame.Shape.HLine);box.addWidget(line)
        self.heading=QLabel();self.heading.setWordWrap(True);self.heading.setStyleSheet('font-weight:650;color:#a6f4cf');box.addWidget(self.heading)
        self.empty=QLabel('在四栏中选择音符或时间条，\n或拖出新的时间条。');self.empty.setWordWrap(True);box.addWidget(self.empty)
        self.fields=QWidget();box.addWidget(self.fields);detail=QVBoxLayout(self.fields);detail.setContentsMargins(0,2,0,0)
        self.form=QFormLayout();detail.addLayout(self.form);self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.start=number();self.end=number();self.form.addRow('起始拍',self.start);self.form.addRow('结束拍',self.end)
        self.values=[number() for _ in range(4)]
        for label,v in zip(('起始值','结束值','起始 Y','结束 Y'),self.values):self.form.addRow(label,v);v.valueChanged.connect(self.curve_changed)
        self.ease=QComboBox();self.ease.addItems(EASE_NAMES);self.ease.setMinimumContentsLength(4)
        self.form.addRow('缓动',self.ease);self.ease.currentIndexChanged.connect(self.curve_changed)
        self.graph=CurvePreview();detail.addWidget(self.graph)
        self.apply_button=button(detail,'应用修改',self.apply)
        edits=row(box);self.copy_button=button(edits,'复制',lanes.copy_selected);button(edits,'粘贴',lanes.paste_selected);self.delete_button=button(edits,'删除选中',lanes.delete_selected)
        box.addStretch()
    def rename(self):
        self.lanes.rename_target(self.name.text().strip())
    def apply_section(self):
        l=self.lanes;l.pause();r=l.region;start=self.range_start.value();end=self.range_end.value()
        if not 0<=start<end<=l.doc.end_beat+.00001:
            l.hint.setText('段落起拍和终拍须在谱面内，且终拍晚于起拍。');return
        l.editor.checkpoint()
        l.doc.set_region(start,end,r.rects,self.range_name.text(),r.motions,r.events,r.names)
        l.editor.seek(start);l.changed()
    def open_rectangles(self):
        e=self.lanes.editor
        if not e.region_dirty:e.load_region_draft(self.lanes.region)
        e.advanced_regions.setChecked(True);e.open_inspector(1)
    def objects(self):
        l=self.lanes;r=l.region
        self.title.setText('区域管理   ·   E 切换' if l.region_mode else '轨道管理   ·   E 切换')
        self.sections.setVisible(l.region_mode);self.segment.setVisible(l.region_mode)
        self.range_box.setVisible(l.region_mode and self.segment.isChecked())
        if l.region_mode:
            self.sections.clear()
            for section in l.doc.regions:self.sections.addItem(f'{section.label} · {section.start:g}–{section.end:g} 拍',section.start)
            self.sections.setCurrentIndex(next(i for i,v in enumerate(l.doc.regions) if v is r))
            self.range_name.setText(r.label)
            for w,value in ((self.range_start,r.start),(self.range_end,r.end)):
                w.setDecimals(8);w.setRange(0,l.doc.end_beat);w.setSingleStep(l.doc.step);w.setValue(value)
        self.target_name()
    def target_name(self):
        l=self.lanes;r=l.region
        self.name.setText((r.names[l.index] if r.names else f'区域 {l.index+1}') if l.region_mode and r.rects else '' if l.region_mode else l.track.name)
        self.name.setEnabled(not l.region_mode or bool(r.rects))
        self.remove.setEnabled(len(r.rects if l.region_mode else l.doc.lines)>1)
    def selection(self):
        l=self.lanes;key=l.selected
        self.fields.setVisible(key is not None);self.empty.setVisible(key is None)
        self.copy_button.setEnabled(bool(l.selection));self.delete_button.setEnabled(bool(l.selection))
        if key is None:
            self.heading.setText(f'已选 {len(l.selection)} 项' if l.selection else '事件属性');return
        prop,_=key;item=l.selected_item();note=prop=='notes';self.loading=True
        try:
            self.heading.setText(('Hold' if item.length else 'Tap')+' 音符' if note else l.LABELS[l.PROPS.index(prop)]+'事件')
            for w,val in [(self.start,item.beat if note else item['start']),(self.end,item.beat+item.length if note else item['end'])]:
                w.setRange(0,l.doc.end_beat);w.setSingleStep(l.doc.step);w.setValue(val)
            for i,w in enumerate(self.values):self.form.setRowVisible(w,not note and (i<2 or prop=='center'))
            self.form.setRowVisible(self.ease,not note);self.graph.setVisible(not note)
            if not note:
                factor=display_factor(prop);vector=prop=='center'
                low,high=display_range(prop)
                for i,w in enumerate(self.values[:4 if vector else 2]):
                    v=item['to' if i%2 else 'from'];w.setRange(low,high);w.setSingleStep(.01 if prop in ('alpha','speed') else 1)
                    w.setValue((v[i//2] if vector else v)*factor)
                for i in range(2):self.form.labelForField(self.values[i]).setText(('起始' if i==0 else '结束')+(' X' if vector else {'angle':'角度','width':'长度','height':'宽度','speed':'流速','alpha':'透明度','x':'位置'}[prop]))
                self.ease.setCurrentIndex(EASES.index(item.get('ease','linear')))
        finally:self.loading=False
        self.curve_changed()
    def curve_changed(self,*_):
        key=self.lanes.selected
        if self.loading or key is None or key[0]=='notes':return
        v=self.values;self.graph.values=[(v[0].value(),v[1].value())]
        if key[0]=='center':self.graph.values.append((v[2].value(),v[3].value()))
        self.graph.ease=EASES[self.ease.currentIndex()];self.graph.update()
    def apply(self):
        l=self.lanes
        if not l.selected:return
        prop,index=l.selected
        for w in (self.start,self.end,*self.values):w.interpretText()
        start,end=self.start.value(),self.end.value()
        if prop=='notes':l.update_note(l.selected_item(),start,end);return
        v=[w.value()/display_factor(prop) for w in self.values];vector=prop=='center'
        event=dict(start=start,end=end,**{'from':[v[0],v[2]] if vector else v[0],'to':[v[1],v[3]] if vector else v[1]},ease=EASES[self.ease.currentIndex()])
        if end>start:l.store_event(prop,event,index)
        else:l.hint.setText('结束拍必须晚于起始拍。')
