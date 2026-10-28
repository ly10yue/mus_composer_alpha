"""Per-rectangle keyframe editor with an isolated live draft preview."""
import copy
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,QDoubleSpinBox,QComboBox,QTreeWidget,QTreeWidgetItem,QDialogButtonBox,QMessageBox
from motion import pose,validate_motions,EASINGS
from views import Stage
from numeric import NumberBox,sync_number

class MotionDialog(QDialog):
    def __init__(self,editor,index):
        super().__init__(editor);self.editor=editor;self.index=index;self.setWindowTitle(f'矩形 {index+1} · 移动 / 旋转关键帧');self.resize(850,690)
        self.frames=copy.deepcopy(editor.stage.motions[index] if editor.stage.motions else [])
        layout=QVBoxLayout(self);columns=QHBoxLayout();layout.addLayout(columns,1);left=QVBoxLayout();right=QVBoxLayout();columns.addLayout(left,1);columns.addLayout(right,1)
        hint=QLabel('位移相对原始矩形中心，正 X 向右、正 Y 向下。\n角度正值顺时针；缓动作用于本帧到下一帧。');hint.setWordWrap(True);left.addWidget(hint)
        self.keys=QTreeWidget();self.keys.setHeaderLabels(['拍','X / Y','角度','缓动']);self.keys.setRootIsDecorated(False);self.keys.itemClicked.connect(self.select_key);left.addWidget(self.keys,1)
        form=QFormLayout();self.beat=self.number(0,600000,4,editor.doc.step);self.x=self.number(-2,2,4,.05);self.y=self.number(-2,2,4,.05);self.angle=self.number(-36000,36000,2,15)
        self.ease=QComboBox();self.ease.addItems(['匀速','平滑','保持 / 瞬移'])
        for label,widget in [('拍位置',self.beat),('横向位移 X',self.x),('纵向位移 Y',self.y),('旋转角度 °',self.angle),('到下一帧',self.ease)]:form.addRow(label,widget)
        left.addLayout(form)
        row=QHBoxLayout();self.write_button=self.button('写入 / 更新关键帧',self.write_key,row);self.button('删除选中帧',self.delete_key,row);left.addLayout(row)
        row=QHBoxLayout();self.button('在游标处添加帧',self.add_current,row);self.button('添加段落起止帧',self.seed,row);left.addLayout(row)
        self.preview=Stage(editor);self.preview.editing=True;self.preview.motion_preview=True;self.preview.rects=copy.deepcopy(editor.stage.rects);self.preview.motions=copy.deepcopy(editor.stage.motions or [[] for _ in self.preview.rects]);self.preview.selected=index;self.preview.aspect=editor.stage.aspect;right.addWidget(self.preview,1)
        self.time=QLabel();right.addWidget(self.time)
        self.preview_beat=self.number(0,editor.doc.end_beat,3,editor.doc.step);self.preview_beat.valueChanged.connect(editor.seek);right.addWidget(QLabel('预览拍（仅预览此区域草稿）'));right.addWidget(self.preview_beat)
        row=QHBoxLayout();self.play=self.button('播放 / 暂停',editor.toggle_play,row);self.button('回到段落起点',lambda:editor.seek(editor.area_start.value()),row);right.addLayout(row)
        note=QLabel('先写入关键帧，再定位或播放查看运动。\n首帧前、末帧后保持该帧状态。\n无关键帧表示静态矩形；只有一帧时为固定变换。\n确定后仍需在主界面点击“应用时间段”。');note.setWordWrap(True);right.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(33);self.refresh();self.tick()
    @staticmethod
    def number(low,high,decimals,step):
        s=NumberBox();s.setRange(low,high);s.setDecimals(decimals);s.setSingleStep(step);return s
    @staticmethod
    def button(label,fn,layout):
        b=QPushButton(label);b.clicked.connect(fn);layout.addWidget(b);return b
    def tick(self):
        self.preview.update();self.time.setText(f'当前拍 {self.editor.cursor:.3f} · 矩形 {self.index+1}')
        sync_number(self.preview_beat,self.editor.cursor)
    def refresh(self):
        self.keys.clear()
        for i,f in enumerate(self.frames):
            item=QTreeWidgetItem([f"{f['beat']:g}",f"{f['x']:g} / {f['y']:g}",f"{f['angle']:g}",['匀速','平滑','保持'][EASINGS.index(f.get('ease','linear'))]]);item.setData(0,Qt.ItemDataRole.UserRole,i);self.keys.addTopLevelItem(item)
        for col in range(4):self.keys.resizeColumnToContents(col)
        self.preview.motions[self.index]=copy.deepcopy(self.frames);self.preview.update()
    def select_key(self,item,column=0):
        f=self.frames[item.data(0,Qt.ItemDataRole.UserRole)]
        for widget,key in [(self.beat,'beat'),(self.x,'x'),(self.y,'y'),(self.angle,'angle')]:widget.setValue(f[key])
        self.ease.setCurrentIndex(EASINGS.index(f.get('ease','linear')));self.editor.seek(f['beat'])
    def write_key(self):
        f=dict(beat=self.beat.value(),x=self.x.value(),y=self.y.value(),angle=self.angle.value(),ease=EASINGS[self.ease.currentIndex()])
        frames=copy.deepcopy(self.frames);item=self.keys.currentItem()
        if item is not None:frames.pop(item.data(0,Qt.ItemDataRole.UserRole))
        frames=[k for k in frames if abs(k['beat']-f['beat'])>1e-7];frames.append(f);frames.sort(key=lambda k:k['beat'])
        try:validate_motions([frames],1)
        except ValueError as ex:QMessageBox.warning(self,'关键帧无效',str(ex));return
        self.frames=frames;self.refresh();self.editor.seek(f['beat'])
    def add_current(self):
        beat=self.editor.doc.snap(self.editor.cursor);x,y,angle=pose(self.frames,beat);self.keys.clearSelection();self.keys.setCurrentItem(None)
        for widget,value in [(self.beat,beat),(self.x,x),(self.y,y),(self.angle,angle)]:widget.setValue(value)
        self.write_key()
    def seed(self):
        if len(self.frames)>254:QMessageBox.warning(self,'关键帧过多','每个矩形最多 256 帧');return
        for beat in (self.editor.area_start.value(),self.editor.area_end.value()):
            if not any(abs(f['beat']-beat)<1e-7 for f in self.frames):
                x,y,angle=pose(self.frames,beat);self.frames.append(dict(beat=beat,x=x,y=y,angle=angle,ease='linear'));self.frames.sort(key=lambda f:f['beat'])
        self.refresh()
    def delete_key(self):
        item=self.keys.currentItem()
        if item is not None:self.frames.pop(item.data(0,Qt.ItemDataRole.UserRole));self.refresh()
    def done(self,result):
        self.timer.stop();self.editor.player.pause();super().done(result)
