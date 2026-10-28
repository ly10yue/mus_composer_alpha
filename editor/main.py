from __future__ import annotations
import copy
import hashlib
import json
import os
import filecmp,shutil
from pathlib import Path
import sys
import tempfile
import uuid

from PySide6.QtCore import Qt, QTimer, QUrl, QStandardPaths,Signal
from PySide6.QtGui import QAction, QKeySequence, QFont, QShortcut
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QComboBox, QSpinBox, QDoubleSpinBox, QFileDialog, QMessageBox, QInputDialog,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QCheckBox, QTreeWidget, QTreeWidgetItem,
    QTabWidget, QSlider, QGroupBox, QAbstractItemView, QScrollArea, QLayout, QPlainTextEdit,QMenu)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from model import Document, History, Note, FULL, DIVISIONS, atomic_json, export_package, import_package, validate_rects
from views import Timeline, Stage
from motion import validate_motions
from motion_dialog import MotionDialog
from region_editor import RegionDialog
from versioning import APP_VERSION,scale_spatial
from region_events import validate_region_events
from timeline_edit import write_clipboard,read_clipboard,shifted_items,append_notes
from dataclasses import asdict
from track_editor import TrackDialog
from agent_panel import AgentPanel
from audio import Waveform
from hit_audio import ComposerHits
from numeric import NumberBox,sync_number
from tracks import Track
from playback_clock import PlaybackClock

STYLE='''
QMainWindow, QWidget { background:#10191b; color:#edf5eb; font: 10pt "Microsoft YaHei UI"; }
QMenuBar, QMenu { background:#182527; } QMenu::item:selected { background:#315145; }
QPushButton { background:#203033; border:1px solid #354c4d; border-radius:5px; padding:7px 12px; }
QPushButton:hover { border-color:#a6f4cf; background:#2b413c; }
QPushButton:checked, QPushButton[primary="true"] { background:#a6f4cf; color:#10191b; border-color:#a6f4cf; font-weight:600; }
QPushButton:disabled { color:#536b6c; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { padding:5px; border:1px solid #354c4d; border-radius:4px; background:#182527; }
QComboBox QAbstractItemView { background:#182527; selection-background-color:#315145; }
QGroupBox { border:1px solid #304244; border-radius:5px; margin-top:12px; padding:12px 6px 5px; }
QGroupBox::title { subcontrol-origin:margin; left:10px; color:#a6f4cf; }
QTabWidget::pane { border:1px solid #304244; } QTabBar::tab { background:#182527; padding:8px 14px; } QTabBar::tab:selected { color:#a6f4cf; border-bottom:2px solid #a6f4cf; }
QTreeWidget { border:1px solid #304244; background:#142022; alternate-background-color:#19292b; }
QTreeWidget::item:selected { background:#315145; } QHeaderView::section { background:#203033; color:#8da5a4; border:0; padding:5px; }
QScrollBar:vertical { background:#142022; width:12px; } QScrollBar::handle:vertical { background:#43645d; min-height:30px; } QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QSlider::groove:horizontal { background:#304244; height:4px; } QSlider::handle:horizontal { background:#a6f4cf; width:12px; margin:-5px 0; border-radius:5px; }
QPlainTextEdit { background:#142022; border:1px solid #354c4d; border-radius:4px; padding:4px; selection-background-color:#315145; }
QToolTip { background:#203033; color:#edf5eb; border:1px solid #a6f4cf; }
'''
_icons=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'ui_assets'
STYLE+='''
QSpinBox, QDoubleSpinBox { padding-right:26px; min-height:22px; }
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin:border; subcontrol-position:top right; width:22px; height:16px; background:#24383a; border-left:1px solid #354c4d; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin:border; subcontrol-position:bottom right; width:22px; height:16px; background:#24383a; border-left:1px solid #354c4d; }
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover { background:#3a5951; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image:url("UP_ICON"); width:10px; height:6px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image:url("DOWN_ICON"); width:10px; height:6px; }
'''.replace('UP_ICON',(_icons/'arrow-up.svg').as_posix()).replace('DOWN_ICON',(_icons/'arrow-down.svg').as_posix())

def spin(value=0,maximum=100000,decimals=4,minimum=0):
    s=NumberBox();s.setDecimals(decimals);s.setRange(minimum,maximum);s.setSingleStep(.01 if maximum-minimum<=2 else 1);s.setValue(value);return s

def new_document():return Document(lines=[Track('line1','轨迹 1',[dict(beat=0.,x=.5,alpha=0.,ease='linear')])])

class Editor(QMainWindow):
    frameRendered=Signal()
    def __init__(self, recovery=True):
        super().__init__();self.setWindowTitle('INTERVAL Composer · 制谱器');self.setMinimumSize(1024,640)
        available=QApplication.primaryScreen().availableGeometry();self.resize(max(1024,min(1440,available.width()-40)),max(640,min(940,available.height()-60)))
        self.cache=Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation));self.cache.mkdir(parents=True,exist_ok=True)
        self.preview_options=dict(gain=150,scroll=1.6,enabled=True)
        try:
            settings=json.loads((self.cache/'preview-settings.json').read_text(encoding='utf-8'))
            if type(settings.get('gain')) is int and 0<=settings['gain']<=200:self.preview_options['gain']=settings['gain']
            if type(settings.get('scroll')) in (int,float) and .5<=settings['scroll']<=4:self.preview_options['scroll']=float(settings['scroll'])
            if type(settings.get('enabled')) is bool:self.preview_options['enabled']=settings['enabled']
        except (OSError,ValueError,TypeError,AttributeError):pass
        self.scroll_factor=self.preview_options['scroll'];self.preview_save_timer=QTimer(self);self.preview_save_timer.setSingleShot(True);self.preview_save_timer.timeout.connect(self.save_preview_options)
        self.recovery_path=self.cache/'recovery.ivproj'
        self.doc=new_document();self.history=History();self.selection=set();self.clipboard=[];self.cursor=0.;self.tool='select';self.x_grid=4;self.dirty=False;self.path=None;self.loop_a=0.;self.loop_b=4.;self.last_tick=-1;self.region_dirty=False;self.audio_loaded=False
        self.clock=PlaybackClock();self.player=QMediaPlayer(self);self.output=QAudioOutput(self);self.output.setVolume(1.);self.player.setAudioOutput(self.output)
        self.player.positionChanged.connect(self.position_changed);self.player.durationChanged.connect(self.duration_changed)
        self.player.playbackStateChanged.connect(self.playback_state_changed);self.player.playbackRateChanged.connect(self.clock.set_rate)
        self.player.errorOccurred.connect(lambda *_:self.statusBar().showMessage('音频错误：'+self.player.errorString(),15000))
        self.player.mediaStatusChanged.connect(self.media_status)
        self.player.playbackStateChanged.connect(lambda *_:self.play_button.setText('Ⅱ 暂停' if self.playing() else '▶ 播放'))
        self.waveform=Waveform(self);self.waveform.changed.connect(lambda:self.timeline.viewport().update() if QApplication.activeModalWidget() is None else None);self.waveform.failed.connect(lambda msg:self.statusBar().showMessage('波形不可用，播放和编辑仍可使用：'+msg,8000))
        self.hit_audio=ComposerHits(self)
        self.build_ui();self.build_shortcuts()
        self.render_timer=QTimer(self);self.render_timer.setTimerType(Qt.TimerType.PreciseTimer);self.render_timer.timeout.connect(self.render_frame);self.render_timer.start(16)
        self.autosave_timer=QTimer(self);self.autosave_timer.timeout.connect(self.autosave);self.autosave_timer.start(20000)
        self.sync()
        if recovery and self.recovery_path.exists():QTimer.singleShot(0,self.offer_recovery)

    @property
    def peaks(self):return self.waveform.peaks
    def button(self,label,callback,layout,primary=False):
        b=QPushButton(label);b.setProperty('primary',primary);b.clicked.connect(callback);layout.addWidget(b);return b
    def build_ui(self):
        root=QWidget();self.setCentralWidget(root);outer=QVBoxLayout(root);outer.setContentsMargins(20,12,20,12);outer.setSpacing(10)
        top=QHBoxLayout();brand=QLabel('▥  INTERVAL   /   COMPOSER  '+APP_VERSION);brand.setStyleSheet('font-size:20px;font-weight:650;color:#a6f4cf');top.addWidget(brand);top.addStretch();top.addWidget(QLabel('01  ·  BEAT / NOTE / AREA'));outer.addLayout(top)
        files=QHBoxLayout();outer.addLayout(files)
        for label,fn in [('新建',self.new),('打开工程 / 谱面',self.open_dialog),('导入歌曲',self.import_audio),('示例谱面',self.open_demo),('保存工程',self.save),('导出 JSON',self.export_json)]:
            if label=='示例谱面':
                b=QPushButton(label);files.addWidget(b);menu=QMenu(b)
                menu.addAction('基础示例',lambda:self.open_demo());menu.addAction('AT Flow · 4K / 区域 / 综合演出',lambda:self.open_demo('at-flow.json'));b.setMenu(menu)
            else:self.button(label,fn,files)
        self.button('导出 Android 谱面包 ↗',self.export_android,files,True);files.addStretch()
        track=QHBoxLayout();self.track_label=QLabel('未导入歌曲');self.track_label.setStyleSheet('font-size:17px;font-weight:600');track.addWidget(self.track_label,1)
        self.button('歌曲 / BPM / 偏移',self.metadata,track);outer.addLayout(track)
        tools=QHBoxLayout();self.tool_buttons={}
        for tool,label in [('select','选择 V'),('tap','Tap Q'),('hold','Hold R')]:
            b=self.button(label,lambda checked=False,t=tool:self.set_tool(t),tools);b.setCheckable(True);self.tool_buttons[tool]=b
        tools.addSpacing(10);self.grid_basis=QComboBox();self.grid_basis.addItems(['每拍','每小节']);self.grid_basis.currentIndexChanged.connect(self.change_basis);tools.addWidget(self.grid_basis);self.division=QComboBox();self.division.addItems([f'1/{n}' for n in DIVISIONS]);self.division.currentIndexChanged.connect(self.change_division);tools.addWidget(self.division)
        tools.addWidget(QLabel('绑定轨迹'));self.line_combo=QComboBox();self.line_combo.setMinimumWidth(145);tools.addWidget(self.line_combo);self.button('轨迹 / 四栏编辑',self.edit_tracks,tools);self.button('区域 / 四栏编辑',self.edit_regions,tools)
        self.undo_button=self.button('撤销',self.undo,tools);self.redo_button=self.button('重做',self.redo,tools);self.button('检查谱面',self.validate,tools);tools.addStretch();outer.addLayout(tools)
        split=QSplitter();outer.addWidget(split,1);self.timeline=Timeline(self);split.addWidget(self.timeline)
        right=QWidget();rl=QVBoxLayout(right);rl.setContentsMargins(8,0,0,0);rl.setSpacing(6);right.setMinimumWidth(440);right.setMaximumWidth(520)
        self.stage=Stage(self);self.stage.setMinimumHeight(230);self.stage.rectanglesChanged.connect(self.rectangles_changed);self.stage.selectedChanged.connect(self.rect_selected);rl.addWidget(self.stage)
        stagebar=QHBoxLayout();stagebar.addWidget(QLabel('预览比例'));aspect=QComboBox();aspect.addItems(['16:9','4:3']);aspect.currentIndexChanged.connect(lambda i:self.set_aspect(i));stagebar.addWidget(aspect);stagebar.addStretch();rl.addLayout(stagebar)
        self.tabs=QTabWidget();rl.addWidget(self.tabs,1)
        notes=QWidget();nl=QVBoxLayout(notes);nl.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize);self.selection_label=QLabel('未选择音符');nl.addWidget(self.selection_label)
        self.button('音符属性（双击）',self.note_properties,nl)
        self.button('选中音符绑定到当前轨迹',self.bind_notes,nl)
        self.button('按当前网格批量填充',self.fill_notes,nl)
        row=QHBoxLayout();self.button('复制',self.copy_notes,row);self.button('粘贴到游标',self.paste_notes,row);nl.addLayout(row)
        row=QHBoxLayout();self.button('左右镜像',self.mirror,row);self.button('删除选中',self.delete_notes,row);nl.addLayout(row)
        info=QLabel('网格可选按每拍或每小节细分。\n例如 1/6 小节 = 将一小节分成 6 格。\n粗线是小节起点，默认 4 拍一小节。\n\n判定线固定在下方，后面的拍在上方。\nTap：点击放置并绑定所选/最近轨迹。Hold：向上拖出尾部。\n选择：纵拖改时间，横拖换轨迹；拖尾端改长度。\nCtrl 或 Shift 拖框多选；Ctrl+C / V 复制粘贴。\n右键删除；点击左侧刻度定位。\nCtrl + 滚轮缩放，滚轮每次移动一格，播放时音符向下落。');info.setWordWrap(True);info.setStyleSheet('color:#8da5a4;line-height:1.5');nl.addWidget(info);nl.addStretch();note_scroll=QScrollArea();note_scroll.setWidgetResizable(True);note_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);note_scroll.setWidget(notes);self.tabs.addTab(note_scroll,'音符')
        areas=QWidget();al=QVBoxLayout(areas);al.setSpacing(5);al.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.region_list=QTreeWidget();self.region_list.setHeaderLabels(['拍范围','名称','矩形']);self.region_list.setRootIsDecorated(False);self.region_list.setFixedHeight(120);self.region_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.region_list.itemClicked.connect(self.select_region);al.addWidget(self.region_list)
        range_row=QHBoxLayout();self.area_start=spin();self.area_end=spin(4);range_row.addWidget(QLabel('起拍'));range_row.addWidget(self.area_start);range_row.addWidget(QLabel('止拍'));range_row.addWidget(self.area_end);al.addLayout(range_row)
        row=QHBoxLayout();self.button('起点 = 游标',lambda:self.area_start.setValue(self.doc.snap(self.cursor)),row);self.button('终点 = 游标',lambda:self.area_end.setValue(self.doc.snap(self.cursor)),row);al.addLayout(row)
        self.area_label=QLineEdit('自定义区域');self.area_label.setPlaceholderText('区域名称');al.addWidget(self.area_label)
        presets=QHBoxLayout()
        for label,rects in [('全域',FULL),('上半',[[0,0,1,.5]]),('下半',[[0,.5,1,1]]),('双区',[[0,0,.46,1],[.54,0,1,1]])]:self.button(label,lambda checked=False,r=rects:self.preset(r),presets)
        al.addLayout(presets)
        row=QHBoxLayout();self.draw_button=self.button('＋ 拖画矩形',self.toggle_draw,row);self.draw_button.setCheckable(True);self.button('删除矩形',self.delete_rectangle,row);al.addLayout(row)
        motion_row=QHBoxLayout();self.motion_button=self.button('区域 / 四栏编辑',self.edit_motion,motion_row);self.motion_preview=QCheckBox('预览动画');self.motion_preview.toggled.connect(self.preview_motion);motion_row.addWidget(self.motion_preview);al.addLayout(motion_row)
        coords=QHBoxLayout();self.rect_spins=[]
        for title in ['左','上','右','下']:
            col=QVBoxLayout();col.setSpacing(1);col.addWidget(QLabel(title));s=spin(0,100,3);s.setSingleStep(1);s.valueChanged.connect(self.numeric_rect);self.rect_spins.append(s);col.addWidget(s);coords.addLayout(col)
        al.addLayout(coords)
        self.area_hint=QLabel('修改后点击“应用时间段”；未覆盖时段保持原样。');self.area_hint.setWordWrap(True);self.area_hint.setStyleSheet('color:#8da5a4;font-size:11px');al.addWidget(self.area_hint)
        row=QHBoxLayout();self.button('应用时间段',self.apply_region,row,True);self.button('该段恢复全域',self.reset_region,row);al.addLayout(row);al.addStretch();area_scroll=QScrollArea();area_scroll.setWidgetResizable(True);area_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);area_wrapper=QWidget();area_layout=QVBoxLayout(area_wrapper);self.button('区域 / 四栏编辑',self.edit_regions,area_layout,True);region_help=QLabel('像线一样选择、新建和删除区域。默认全屏，角度 0°；确定后直接应用，可整体撤销。');region_help.setWordWrap(True);area_layout.addWidget(region_help);self.advanced_regions=QCheckBox('旧式分段 / 矩形工具');area_layout.addWidget(self.advanced_regions);area_layout.addWidget(areas);areas.setVisible(False);self.advanced_regions.toggled.connect(areas.setVisible);self.advanced_regions.toggled.connect(lambda _:self.tab_changed(self.tabs.currentIndex()));area_layout.addStretch();area_scroll.setWidget(area_wrapper);self.tabs.addTab(area_scroll,'判定区域');self.tabs.currentChanged.connect(self.tab_changed)
        self.agent_panel=AgentPanel(self);self.tabs.addTab(self.agent_panel,'Agent');self.agent_panel.refresh_target()
        self.area_start.valueChanged.connect(self.rectangles_changed);self.area_end.valueChanged.connect(self.rectangles_changed);self.area_label.textEdited.connect(self.rectangles_changed)
        split.addWidget(right);split.setSizes([850,430])
        transport=QHBoxLayout();self.play_button=self.button('▶ 播放',self.toggle_play,transport,True);self.button('回到开头',lambda:self.seek(0),transport)
        self.time_label=QLabel('00:00.000');self.time_label.setMinimumWidth(98);transport.addWidget(self.time_label)
        self.slider=QSlider(Qt.Orientation.Horizontal);self.slider.setRange(0,60000);self.slider.sliderReleased.connect(lambda:self.seek_audio(self.slider.value()/1000));transport.addWidget(self.slider,1)
        self.beat_jump=spin(0,100000,3);self.beat_jump.setMaximumWidth(110);self.beat_jump.valueChanged.connect(self.seek);transport.addWidget(QLabel('拍'));transport.addWidget(self.beat_jump)
        rate=QComboBox();rate.addItems(['0.50×','0.75×','1.00×']);rate.setCurrentIndex(2);rate.currentIndexChanged.connect(lambda i:self.player.setPlaybackRate([.5,.75,1][i]));transport.addWidget(rate)
        self.metronome=QCheckBox('节拍器');self.metronome.toggled.connect(self.hit_audio.request_mix);transport.addWidget(self.metronome);outer.addLayout(transport)
        row=QHBoxLayout();self.loop_check=QCheckBox('循环 A–B');row.addWidget(self.loop_check);self.a_button=self.button('A = 游标',self.set_a,row);self.b_button=self.button('B = 游标',self.set_b,row);self.loop_label=QLabel('0 → 4 拍');row.addWidget(self.loop_label)
        self.hit_enabled=QCheckBox('打击音效');self.hit_enabled.setChecked(self.preview_options['enabled']);row.addWidget(self.hit_enabled)
        self.hit_volume_label=QLabel();row.addWidget(self.hit_volume_label)
        self.hit_volume=QSlider(Qt.Orientation.Horizontal);self.hit_volume.setRange(0,200);self.hit_volume.setValue(self.preview_options['gain']);self.hit_volume.setFixedWidth(95);self.hit_volume.setToolTip('0–200%；100% 为原始音效电平，200% 为两倍振幅');row.addWidget(self.hit_volume)
        row.addWidget(QLabel('流速'));self.scroll_speed=NumberBox();self.scroll_speed.setRange(.5,4);self.scroll_speed.setDecimals(1);self.scroll_speed.setSingleStep(.1);self.scroll_speed.setSuffix('×');self.scroll_speed.setValue(self.scroll_factor);self.scroll_speed.setToolTip('只改变音符和谱面下落速度，不改变音乐速度');row.addWidget(self.scroll_speed)
        self.hit_enabled.toggled.connect(self.configure_preview);self.hit_volume.valueChanged.connect(self.configure_preview);self.scroll_speed.valueChanged.connect(self.configure_preview)
        self.configure_preview();row.addStretch();outer.addLayout(row)
        self.statusBar().showMessage('先导入歌曲或打开示例。工程自动恢复快照每 20 秒保存一次。')
        self.set_tool('select')

    def configure_preview(self):
        self.hit_volume_label.setText(f'音量 {self.hit_volume.value()}%')
        self.hit_audio.bank.configure(self.hit_enabled.isChecked(),self.hit_volume.value()/100)
        self.scroll_factor=self.scroll_speed.value();self.timeline.ppb=64*self.scroll_factor;self.timeline.sync();self.stage.update()
        self.preview_save_timer.start(250)

    def save_preview_options(self):
        try:atomic_json(self.cache/'preview-settings.json',dict(gain=self.hit_volume.value(),scroll=self.scroll_speed.value(),enabled=self.hit_enabled.isChecked()))
        except OSError:self.statusBar().showMessage('试听设置暂时无法保存。',3000)

    def build_shortcuts(self):
        entries={'Ctrl+N':self.new,'Ctrl+O':self.open_dialog,'Ctrl+S':self.save,'Ctrl+Shift+S':self.save_as,'Ctrl+Z':self.undo,'Ctrl+Y':self.redo,'Ctrl+Shift+Z':self.redo,'Ctrl+C':self.copy_notes,'Ctrl+V':self.paste_notes,'Ctrl+A':self.select_all,'Delete':self.delete_notes,'Space':self.toggle_play,'Q':lambda:self.set_tool('tap'),'R':lambda:self.set_tool('hold'),'V':lambda:self.set_tool('select'),'Left':lambda:self.seek(max(0,self.cursor-self.doc.step)),'Right':lambda:self.seek(self.cursor+self.doc.step)}
        self.shortcuts=[]
        for key,fn in entries.items():
            shortcut=QShortcut(QKeySequence(key),self)
            def guarded(fn=fn,key=key):
                if isinstance(QApplication.focusWidget(),(QLineEdit,QDoubleSpinBox,QSpinBox,QPlainTextEdit)) and key in ('Q','R','V','Space','Delete','Left','Right','Ctrl+A','Ctrl+C','Ctrl+V','Ctrl+Z','Ctrl+Y','Ctrl+Shift+Z'):return
                fn()
            shortcut.activated.connect(guarded);self.shortcuts.append(shortcut)
    def message(self,title,text):QMessageBox.information(self,title,text)
    def checkpoint(self):self.history.push(self.doc)
    def changed(self):self.dirty=True;self.hit_audio.invalidate();self.sync();self.selection_changed()
    def sync(self):
        self.beat_jump.setSingleStep(self.doc.step)
        selected=self.line_combo.currentData();self.line_combo.blockSignals(True);self.line_combo.clear();self.line_combo.addItem('自动 · 点击最近轨迹',None)
        for t in self.doc.lines:self.line_combo.addItem(t.name,t.id)
        self.line_combo.setCurrentIndex(max(0,self.line_combo.findData(selected)));self.line_combo.blockSignals(False)
        self.track_label.setText(f'{self.doc.title}   /   {self.doc.bpm:g} BPM   /   {self.doc.meter} 拍一小节')
        self.setWindowTitle(('● ' if self.dirty else '')+self.doc.title+' — INTERVAL Composer '+APP_VERSION)
        self.division.blockSignals(True);self.division.setCurrentIndex(DIVISIONS.index(self.doc.division));self.division.blockSignals(False)
        self.grid_basis.blockSignals(True);self.grid_basis.setCurrentIndex(1 if self.doc.grid_unit=='bar' else 0);self.grid_basis.blockSignals(False)
        self.undo_button.setEnabled(bool(self.history.undo_stack));self.redo_button.setEnabled(bool(self.history.redo_stack));self.timeline.sync();self.stage.update();self.refresh_regions()
    def selection_changed(self):
        selected=[n for n in self.doc.notes if n.id in self.selection];self.selection_label.setText(f'选中 {len(selected)} 个音符'+(f' · 第 {selected[0].beat:g} 拍' if len(selected)==1 else ''));self.timeline.viewport().update()
    def set_tool(self,tool):
        self.tool=tool
        for t,b in self.tool_buttons.items():b.setChecked(t==tool)
        if hasattr(self,'timeline'):self.timeline.viewport().update()
    def placement_line(self,x,beat):
        return self.line_combo.currentData() or self.doc.nearest_line(x,self.cursor,beat)
    def bind_notes(self):
        line=self.line_combo.currentData()
        if not self.selection or line is None:
            self.statusBar().showMessage('先选择音符，并在上方“绑定轨迹”中选择一条具体轨迹。',6000);return
        self.checkpoint()
        for n in self.doc.notes:
            if n.id in self.selection:n.line=line
        self.changed()
    def edit_tracks(self):
        self.hit_audio.pause();dialog=TrackDialog(self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.checkpoint();self.doc.lines=copy.deepcopy(dialog.doc.lines);self.doc.notes=copy.deepcopy(dialog.doc.notes);self.doc.division=dialog.doc.division;self.doc.grid_unit=dialog.doc.grid_unit;self.selection.intersection_update({n.id for n in self.doc.notes});self.changed()

    def set_x_grid(self,value):self.x_grid=value;self.timeline.viewport().update()
    def change_division(self,index):
        if index>=0:self.doc.division=DIVISIONS[index];self.beat_jump.setSingleStep(self.doc.step);self.dirty=True;self.timeline.viewport().update()
    def change_basis(self,index):self.doc.grid_unit='bar' if index==1 else 'beat';self.beat_jump.setSingleStep(self.doc.step);self.dirty=True;self.timeline.viewport().update()
    def undo(self):
        if not self.history.undo_stack:return
        self.doc=self.history.undo(self.doc);self.selection.clear();self.region_dirty=False;self.load_region_draft(self.doc.region_at(self.cursor) or self.doc.regions[0]);self.changed()
    def redo(self):
        if not self.history.redo_stack:return
        self.doc=self.history.redo(self.doc);self.selection.clear();self.region_dirty=False;self.load_region_draft(self.doc.region_at(self.cursor) or self.doc.regions[0]);self.changed()
    def select_all(self):self.selection={n.id for n in self.doc.notes};self.selection_changed()
    def delete_notes(self):
        if not self.selection:return
        self.checkpoint();self.doc.notes=[n for n in self.doc.notes if n.id not in self.selection];self.selection.clear();self.changed()
    def copy_notes(self):
        self.clipboard=copy.deepcopy([n for n in self.doc.notes if n.id in self.selection]);write_clipboard('notes',[dict(prop='notes',data=asdict(n)) for n in self.clipboard]);self.statusBar().showMessage(f'已复制 {len(self.clipboard)} 个音符；粘贴以游标拍为起点。',5000)
    def paste_notes(self):
        try:
            clip=read_clipboard()
            if not clip:return
            if clip['kind'] not in ('notes','track') or any(i['prop']!='notes' for i in clip['items']):raise ValueError('含有时间条的内容请在线编辑页粘贴')
            notes=append_notes(self.doc,shifted_items(clip['items'],self.cursor))
        except (ValueError,TypeError,KeyError) as ex:self.statusBar().showMessage(str(ex),6000);return
        if notes:self.checkpoint();self.doc.notes.extend(notes);self.selection={n.id for n in notes};self.changed()
    def mirror(self):
        if not self.selection:return
        self.checkpoint()
        for n in self.doc.notes:
            if n.id in self.selection:n.line=self.doc.nearest_line(1-self.doc.note_x(n,self.cursor),self.cursor,n.beat)
        self.changed()
    def note_properties(self):
        notes=[n for n in self.doc.notes if n.id in self.selection]
        if len(notes)!=1:self.message('音符属性','请选择单个音符。多选可拖动、复制、镜像或删除。');return
        n=notes[0];dialog=QDialog(self);dialog.setWindowTitle('音符属性');layout=QFormLayout(dialog)
        beat=spin(n.beat);x=QComboBox();[x.addItem(t.name,t.id) for t in self.doc.lines];x.setCurrentIndex(x.findData(n.line));length=spin(n.length);layout.addRow('开始拍',beat);layout.addRow('绑定轨迹',x);layout.addRow('持续拍数（0 = Tap）',length)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addRow(buttons)
        if dialog.exec():self.checkpoint();n.beat=beat.value();n.line=x.currentData();n.length=length.value();self.changed()

    def fill_notes(self):
        dialog=QDialog(self);dialog.setWindowTitle('按网格填充');layout=QFormLayout(dialog);start=spin(self.doc.snap(self.cursor));end=spin(self.doc.snap(self.cursor)+self.doc.meter);x=QComboBox();[x.addItem(t.name,t.id) for t in self.doc.lines];x.setCurrentIndex(max(0,x.findData(self.line_combo.currentData())));length=spin(0)
        layout.addRow('开始拍（包含）',start);layout.addRow('结束拍（不包含）',end);layout.addRow('绑定轨迹',x);layout.addRow('持续拍数（0 = Tap）',length);layout.addRow(QLabel(f'当前间距 {self.doc.step:g} 拍。Hold 长度不得超过间距。'))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addRow(buttons)
        if dialog.exec():
            try:
                before=copy.deepcopy(self.doc);ids=self.doc.fill(start.value(),end.value(),x.currentData(),length.value());self.history.push(before);self.selection=set(ids);self.changed();self.statusBar().showMessage(f'已填充 {len(ids)} 个音符，可整体撤销。',5000)
            except ValueError as ex:self.message('无法填充',str(ex))

    def metadata(self):
        d=QDialog(self);d.setWindowTitle('歌曲与节奏');layout=QFormLayout(d);title=QLineEdit(self.doc.title);artist=QLineEdit(self.doc.artist);difficulty=QLineEdit(self.doc.difficulty);bpm=spin(self.doc.bpm,400,3,20);meter=QSpinBox();meter.setRange(1,16);meter.setValue(self.doc.meter);offset=spin(self.doc.offset,600,4,-600);mode=QComboBox();mode.addItems(['保留拍位置（改变音符实际时间）','保留实际时间（重新计算拍位置）'])
        for label,w in [('标题',title),('作者',artist),('难度',difficulty),('BPM（恒定）',bpm),('每小节拍数',meter),('音乐偏移 / 秒',offset),('修改 BPM 时',mode)]:layout.addRow(label,w)
        layout.addRow(QLabel('正偏移：第 0 拍在音乐开始后出现。'))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);layout.addRow(buttons)
        if d.exec():
            self.player.pause();self.checkpoint();self.doc.retime(bpm.value(),mode.currentIndex()==0);self.doc.title=title.text() or 'Untitled';self.doc.artist=artist.text();self.doc.difficulty=difficulty.text() or 'CUSTOM';self.doc.meter=meter.value();self.doc.offset=offset.value();self.doc.fit_regions();self.seek(self.cursor);self.changed()

    def refresh_regions(self):
        self.region_list.clear()
        for i,r in enumerate(self.doc.regions):
            item=QTreeWidgetItem([f'{r.start:.2f} → {r.end:.2f}',r.label+(' ↻' if any(r.motions) or any(r.events) else ''),str(len(r.rects))]);item.setData(0,Qt.ItemDataRole.UserRole,i);self.region_list.addTopLevelItem(item)
        self.region_list.setColumnWidth(0,142);self.region_list.setColumnWidth(1,95)
    def select_region(self,item,column):
        if self.region_dirty and QMessageBox.question(self,'未应用的区域','放弃当前未应用的矩形修改，切换到所选段落？')!=QMessageBox.StandardButton.Yes:return
        r=self.doc.regions[item.data(0,Qt.ItemDataRole.UserRole)];self.area_start.setValue(r.start);self.area_end.setValue(r.end);self.area_label.setText(r.label);self.stage.rects=copy.deepcopy(r.rects);self.stage.motions=copy.deepcopy(r.motions);self.stage.events=copy.deepcopy(r.events);self.stage.selected=-1;self.region_dirty=False;self.area_hint.setText('修改后点击“应用时间段”；未覆盖时段保持原样。');self.rect_selected();self.seek(r.start)
    def load_region_draft(self,r):
        self.area_start.setValue(r.start);self.area_end.setValue(r.end);self.area_label.setText(r.label);self.stage.rects=copy.deepcopy(r.rects);self.stage.motions=copy.deepcopy(r.motions);self.stage.events=copy.deepcopy(r.events);self.stage.selected=-1;self.region_dirty=False;self.rect_selected()
    def edit_regions(self):
        self.hit_audio.pause()
        if self.region_dirty:self.apply_region()
        if self.region_dirty:return
        dialog=RegionDialog(self,max(0,self.stage.selected))
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.checkpoint();self.doc.regions=copy.deepcopy(dialog.doc.regions);self.doc.division=dialog.doc.division;self.doc.grid_unit=dialog.doc.grid_unit
            self.load_region_draft(self.doc.region_at(dialog.section_start) or self.doc.regions[0]);self.stage.selected=dialog.index if dialog.region.rects else -1;self.rect_selected();self.changed()
    def edit_motion(self):
        i=self.stage.selected
        if i<0:return
        dialog=RegionDialog(self,i,direct=False)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            if not self.stage.motions:self.stage.motions=[[] for _ in self.stage.rects]
            self.stage.events=copy.deepcopy(dialog.region.events);self.doc.division=dialog.doc.division;self.doc.grid_unit=dialog.doc.grid_unit;self.rectangles_changed();self.motion_preview.setChecked(True);self.sync()
    def preview_motion(self,enabled):self.stage.motion_preview=enabled;self.stage.update()
    def tab_changed(self,index):
        self.stage.window=self;self.stage.editing=index==1 and self.advanced_regions.isChecked()
        if hasattr(self,'agent_panel') and self.tabs.currentWidget() is self.agent_panel:self.agent_panel.refresh_target();self.agent_panel.show_preview()
        self.stage.update()
    def set_aspect(self,index):self.stage.aspect=16/9 if index==0 else 4/3;self.stage.update()
    def rectangles_changed(self):self.region_dirty=True;self.area_hint.setText('● 区域及动画草稿尚未应用到谱面，请点击“应用时间段”。');self.stage.update()
    def preset(self,rects):self.stage.rects=copy.deepcopy(rects);self.stage.motions=[];self.stage.events=[];self.motion_preview.setChecked(False);self.stage.selected=0 if rects else -1;self.rectangles_changed();self.rect_selected()
    def toggle_draw(self):self.stage.drawing=self.draw_button.isChecked()
    def delete_rectangle(self):
        if self.stage.selected>=0:
            if self.stage.motions:self.stage.motions.pop(self.stage.selected)
            if self.stage.events:self.stage.events.pop(self.stage.selected)
            self.stage.rects.pop(self.stage.selected);self.stage.selected=-1;self.rectangles_changed();self.rect_selected()
    def rect_selected(self):
        selected=self.stage.selected;values=self.stage.rects[selected] if 0<=selected<len(self.stage.rects) else [0,0,0,0]
        self.motion_button.setEnabled(0<=selected<len(self.stage.rects))
        for s,v in zip(self.rect_spins,values):s.blockSignals(True);s.setValue(v*100);s.setEnabled(selected>=0);s.blockSignals(False)
    def numeric_rect(self):
        i=self.stage.selected
        if i<0:return
        values=[s.value()/100 for s in self.rect_spins]
        try:validate_rects([values])
        except ValueError:self.area_hint.setText('坐标无效：需要左 < 右、上 < 下。');return
        self.stage.rects[i]=values;self.rectangles_changed()
    def apply_region(self):
        try:
            start,end=self.doc.snap(self.area_start.value()),self.doc.snap(self.area_end.value());end=min(end,self.doc.end_beat)
            before=copy.deepcopy(self.doc);self.doc.set_region(start,end,self.stage.rects,self.area_label.text(),self.stage.motions,self.stage.events);self.history.push(before);self.region_dirty=False;self.area_hint.setText('✓ 已应用。时间轴右边色条表示区域段落。');self.changed()
        except ValueError as ex:self.message('无法应用',str(ex))
    def reset_region(self):self.preset(FULL);self.area_label.setText('全域');self.apply_region()

    def render_frame(self):
        if self.playing():
            doc=self.hit_audio.active_doc();self.cursor=self.clock.beat(doc.bpm,doc.offset)
            if self.loop_check.isChecked() and self.cursor>=self.loop_b and self.loop_b>self.loop_a:self.seek(self.loop_a)
            else:self.update_position()
        if QApplication.activeModalWidget() is None:self.stage.update()
        self.frameRendered.emit()
    def playback_state_changed(self,state):
        if state==QMediaPlayer.PlaybackState.PlayingState:self.clock.start(self.player.position()/1000,self.player.playbackRate())
        else:self.clock.pause()
    def playing(self):return self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState
    def toggle_play(self):
        if self.playing() or self.hit_audio.wanted_play:self.hit_audio.pause()
        elif self.doc.audio and Path(self.doc.audio).is_file():self.last_tick=-1;self.hit_audio.play()
        else:self.statusBar().showMessage('请先导入可播放的歌曲，等待音频加载完成。',5000)
    def seek(self,beat):
        self.hit_audio.seek(max(0,min(self.doc.end_beat,float(beat))))
        self.cursor=max(0,min(self.doc.end_beat,float(beat)));seconds=max(0,min(self.doc.duration,self.doc.seconds(self.cursor)+self.doc.offset));self.clock.reset(seconds,self.playing(),self.player.playbackRate());self.player.setPosition(round(seconds*1000));self.last_tick=-1;self.update_position();self.timeline.ensure_beat(self.cursor)
    def seek_audio(self,seconds):self.seek(max(0,(seconds-self.doc.offset)*self.doc.bpm/60))
    def position_changed(self,ms):
        if self.playing() and ms==self.player.position():self.clock.observe(ms/1000)
    def update_position(self):
        if QApplication.activeModalWidget() is not None:return
        seconds=self.doc.seconds(self.cursor)+self.doc.offset;self.time_label.setText(f'{int(max(0,seconds))//60:02d}:{max(0,seconds)%60:06.3f}')
        sync_number(self.beat_jump,self.cursor)
        if not self.slider.isSliderDown():self.slider.setValue(int(max(0,seconds)*1000))
        self.timeline.ensure_beat(self.cursor);self.stage.update()
    def duration_changed(self,ms):
        if ms>0:
            duration=ms/1000
            if abs(self.doc.duration-duration)>.01:self.doc.duration=duration;self.doc.fit_regions();self.dirty=True
            self.slider.setRange(0,ms);self.timeline.sync()
    def media_status(self,status):
        if self.hit_audio.media_status(status):return
        if status in (QMediaPlayer.MediaStatus.LoadedMedia,QMediaPlayer.MediaStatus.BufferedMedia):self.audio_loaded=True;self.player.setPosition(int(max(0,self.doc.seconds(self.cursor)+self.doc.offset)*1000))
        elif status==QMediaPlayer.MediaStatus.InvalidMedia:self.audio_loaded=False
    def set_a(self):self.loop_a=self.doc.snap(self.cursor);self.loop_label.setText(f'{self.loop_a:g} → {self.loop_b:g} 拍')
    def set_b(self):
        value=self.doc.snap(self.cursor)
        if value<=self.loop_a:self.statusBar().showMessage('循环 B 必须晚于 A。',5000);return
        self.loop_b=value;self.loop_label.setText(f'{self.loop_a:g} → {self.loop_b:g} 拍')
    def load_audio(self):
        self.player.stop();self.player.setSource(QUrl());self.audio_loaded=False;self.waveform.decoder.stop();self.waveform.peaks=[]
        self.hit_audio.load_document()
        if not self.doc.audio or not Path(self.doc.audio).is_file():self.statusBar().showMessage('歌曲未关联：请点击“导入歌曲”重新关联。',10000)
    def audio_prepared(self,path,duration,converted):
        if self.doc.audio!=path:self.doc.audio=path;self.dirty=True
        # The player loads only the final shared preview, after canonical Ogg
        # decoding. Two overlapping source loads can lose a pending Play request.
        self.duration_changed(round(duration*1000))
        if converted:self.statusBar().showMessage('已转换为 Ogg；原始歌曲保留。正在准备同步试听…')
    def import_audio(self):
        path,_=QFileDialog.getOpenFileName(self,'导入或重新关联歌曲','','音频 (*.ogg *.mp3 *.wav *.m4a *.flac *.aac);;所有文件 (*)')
        if not path:return
        self.doc.audio=str(Path(path).resolve())
        if self.doc.title=='Untitled':self.doc.title=Path(path).stem
        # Audio changes form a new undo boundary so chart history never points to another song.
        self.history=History();self.dirty=True;self.load_audio();self.sync()

    def maybe_save(self):
        if self.region_dirty:
            if QMessageBox.question(self,'区域草稿未应用','放弃未应用的矩形草稿并继续？')!=QMessageBox.StandardButton.Yes:return False
        if not self.dirty:return True
        answer=QMessageBox.question(self,'保存修改','保存当前工程修改？',QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel)
        if answer==QMessageBox.StandardButton.Cancel:return False
        return bool(self.save()) if answer==QMessageBox.StandardButton.Save else True
    def new(self):
        if self.maybe_save():self.replace_document(new_document(),None)
    def replace_document(self,doc,path):
        self.agent_panel.reset_document()
        self.player.stop();self.clipboard=[];self.doc=doc;self.path=Path(path) if path else None;self.history=History();self.selection.clear();self.cursor=0;self.dirty=False;self.stage.rects=copy.deepcopy(FULL);self.stage.motions=[];self.stage.events=[];self.motion_preview.setChecked(False);self.stage.selected=-1;self.area_start.setValue(0);self.area_end.setValue(4);self.loop_check.setChecked(False);self.loop_a=0;self.loop_b=4;self.loop_label.setText('0 → 4 拍');self.region_dirty=False;self.area_hint.setText('修改后点击“应用时间段”；未覆盖时段保持原样。');self.load_audio();self.sync();self.update_position();self.timeline.ensure_beat(0);self.rect_selected()
    def open_dialog(self):
        if not self.maybe_save():return
        path,_=QFileDialog.getOpenFileName(self,'打开工程或谱面','','INTERVAL 文件 (*.ivproj *.interval *.json);;所有文件 (*)')
        if path:self.open_path(path)
    def open_path(self,path):
        try:
            path=Path(path).resolve()
            if path.suffix.lower()=='.interval':doc=import_package(path,self.cache/'imports'/uuid.uuid4().hex);project_path=None
            else:
                if path.stat().st_size>8*1024*1024:raise ValueError('工程 / JSON 文件过大')
                data=json.loads(path.read_text(encoding='utf-8-sig'))
                if data.get('format')=='interval-project':doc=Document.from_project(data,path.parent);project_path=path
                else:doc=Document.from_chart(data,str(path.parent/data['audio']));project_path=None
            self.replace_document(doc,project_path)
        except Exception as ex:self.message('打开失败',str(ex))
    def open_demo(self,filename='demo.json'):
        if not self.maybe_save():return
        base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
        self.open_path(base/'app/src/main/assets'/filename)
    def save(self):
        if self.hit_audio.preparing:self.statusBar().showMessage('歌曲正在转换为 Ogg，完成后即可保存。',6000);return False
        if self.region_dirty:self.message('区域草稿尚未应用','请先点击“应用时间段”再保存工程。');return False
        if self.path is None:return self.save_as()
        try:
            atomic_json(self.path,self.doc.project());self.dirty=False;self.sync();self.recovery_path.unlink(missing_ok=True);self.statusBar().showMessage('已保存工程：'+str(self.path),6000);return True
        except Exception as ex:self.message('保存失败',str(ex));return False
    def save_as(self):
        path,_=QFileDialog.getSaveFileName(self,'保存工程',str(self.path or Path.home()/(self.doc.title+'.ivproj')),'INTERVAL 工程 (*.ivproj)')
        if not path:return False
        self.path=Path(path if path.lower().endswith('.ivproj') else path+'.ivproj');return self.save()
    def autosave(self):
        if not (self.dirty or self.region_dirty):return
        try:
            data=self.doc.project();data['source_path']=str(self.path) if self.path else ''
            if self.region_dirty:data['areaDraft']=dict(start=self.area_start.value(),end=self.area_end.value(),label=self.area_label.text(),rects=self.stage.rects,motions=self.stage.motions,events=self.stage.events)
            if self.region_dirty:data['areaDraft']=scale_spatial({'regions':[copy.deepcopy(data['areaDraft'])]},100,True)['regions'][0]
            atomic_json(self.recovery_path,data)
            self.statusBar().showMessage('已保存自动恢复快照',2500)
        except OSError as ex:self.statusBar().showMessage('自动恢复快照写入失败：'+str(ex),10000)
    def offer_recovery(self):
        if QMessageBox.question(self,'恢复未保存工程','发现上次未正常关闭前的自动恢复快照，是否恢复？')==QMessageBox.StandardButton.Yes:
            try:
                data=json.loads(self.recovery_path.read_text(encoding='utf-8'));self.replace_document(Document.from_project(data),data.get('source_path') or None);self.dirty=True
                if 'areaDraft' in data:
                    draft=scale_spatial({'regions':[copy.deepcopy(data['areaDraft'])]},.01 if data.get('version')==6 else 1,True)['regions'][0];validate_rects(draft['rects']);validate_motions(draft.get('motions',[]),len(draft['rects']));self.area_start.setValue(draft['start']);self.area_end.setValue(draft['end']);self.area_label.setText(draft['label']);self.stage.rects=copy.deepcopy(draft['rects']);self.stage.motions=copy.deepcopy(draft.get('motions',[]));validate_region_events(draft.get('events',[]),len(draft['rects']));self.stage.events=copy.deepcopy(draft.get('events',[]));self.tabs.setCurrentIndex(1);self.rectangles_changed()
                self.sync()
            except Exception as ex:self.message('恢复失败',str(ex))
    def validate(self):
        errors,warnings=self.doc.validate();text=f'{len(self.doc.notes)} 个音符 · {len(self.doc.regions)} 个区域段\n\n'
        text+='错误：\n'+'\n'.join(errors[:30]) if errors else '✓ 没有阻止导出的错误。'
        if warnings:text+='\n\n提示：\n'+'\n'.join(warnings[:20])
        self.message('谱面检查',text)
    def export_ready(self):
        if self.hit_audio.preparing or self.hit_audio.audio_error:
            self.statusBar().showMessage('请等待歌曲转换为 Ogg 完成，转换失败时请重新导入歌曲。',8000);return False
        if self.region_dirty:self.message('区域尚未应用','请先应用区域草稿，或选择其他段落放弃草稿，再导出。');return False
        errors,warnings=self.doc.validate()
        if errors:self.message('请先修正谱面','\n'.join(errors[:20]));return False
        if warnings and QMessageBox.question(self,'导出提示','\n'.join(warnings[:12])+'\n\n仍然导出？')!=QMessageBox.StandardButton.Yes:return False
        return True
    def export_json(self):
        if not self.export_ready():return
        path,_=QFileDialog.getSaveFileName(self,'导出游戏 JSON',self.doc.title+'.json','JSON (*.json)')
        if path:
            try:
                audio=Path(self.doc.audio);name=audio.name
                if audio.resolve().parent==self.hit_audio.conversion_folder.resolve():
                    target=Path(path).parent/name
                    if target.exists() and not filecmp.cmp(audio,target,shallow=False):target=target.with_name(audio.stem+'-'+uuid.uuid4().hex[:8]+'.ogg')
                    if not target.exists():shutil.copy2(audio,target)
                    name=target.name
                atomic_json(path,self.doc.chart(name));self.statusBar().showMessage('JSON 已导出；转换后的 Ogg 已随 JSON 保存。原始 Ogg 歌曲请保持与 JSON 同目录。',12000)
            except Exception as ex:self.message('导出失败',str(ex))
    def export_android(self):
        if not self.export_ready():return
        path,_=QFileDialog.getSaveFileName(self,'导出 Android 谱面包',self.doc.title+'.interval','INTERVAL 谱面包 (*.interval)')
        if path:
            try:
                if not path.lower().endswith('.interval'):path+='.interval'
                export_package(self.doc,path);self.message('导出完成','已包含歌曲和谱面。\n\n将 .interval 文件传入 Android，在游戏主页点击“导入谱面”即可游玩。\n\n'+path)
            except Exception as ex:self.message('导出失败',str(ex))
    def closeEvent(self,event):
        if self.maybe_save():
            self.save_preview_options();self.agent_panel.client.cancel();self.hit_audio.close();self.player.stop();self.waveform.decoder.stop();self.recovery_path.unlink(missing_ok=True);event.accept()
        else:event.ignore()

def main():
    verify_settings=len(sys.argv)>2 and sys.argv[1]=='--verify-agent-settings-output'
    verify=len(sys.argv)>2 and sys.argv[1] in ('--verify-output','--verify-agent-output','--verify-tracks-output','--verify-audio-output','--verify-regions-output')
    verify_audio=verify and sys.argv[1]=='--verify-audio-output'
    verify_regions=verify and sys.argv[1]=='--verify-regions-output'
    verify_tracks=verify and sys.argv[1]=='--verify-tracks-output'
    verify_agent=verify and sys.argv[1]=='--verify-agent-output'
    app=QApplication(sys.argv);app.setApplicationName('IntervalComposerVerification' if verify else 'IntervalComposer');app.setOrganizationName('Interval');app.setStyleSheet(STYLE);app.setFont(QFont('Microsoft YaHei UI',10))
    window=Editor(recovery=len(sys.argv)<2)
    if verify or verify_settings:window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    window.show()
    if verify_settings:
        report=Path(sys.argv[2]).resolve();report.parent.mkdir(parents=True,exist_ok=True)
        def check_settings():
            result=dict(ok=False,frozen=bool(getattr(sys,'frozen',False)))
            def inspect():
                dialog=app.activeModalWidget()
                try:
                    model=dialog.findChild(QLineEdit,'agentModel');key=dialog.findChild(QLineEdit,'agentApiKey')
                    result.update(model=model.text(),key_filled=bool(key.text()),key_masked=key.echoMode()==QLineEdit.EchoMode.Password)
                    dialog.grab().save(str(report.with_suffix('.png')))
                    result['ok']=bool(result['model']) and result['key_filled'] and result['key_masked']
                finally:
                    if dialog:dialog.reject()
            QTimer.singleShot(200,inspect);window.agent_panel.settings()
            atomic_json(report,result);window.dirty=False;window.region_dirty=False;window.close();app.exit(0 if result['ok'] else 1)
        QTimer.singleShot(0,check_settings)
    elif verify_audio:
        report=Path(sys.argv[2]).resolve();report.parent.mkdir(parents=True,exist_ok=True);window.output.setVolume(0)
        window.doc.audio=str(Path(sys.argv[3]).resolve());window.doc.add(1,'line1');window.load_audio();attempts=[0]
        def finish_audio():
            from audio_import import valid_conversion
            passed=window.hit_audio.mix_ready and valid_conversion(window.doc.audio) and window.cursor>1.5 and not window.hit_audio.audio_error
            atomic_json(report,dict(ok=passed,frozen=bool(getattr(sys,'frozen',False)),audio=window.doc.audio,duration=window.doc.duration,beat=window.cursor,hitSoundsPlayed=window.hit_audio.bank.played_count,error=window.hit_audio.audio_error))
            window.dirty=False;window.region_dirty=False;window.close();app.exit(0 if passed else 1)
        def start_audio():
            attempts[0]+=1
            if window.hit_audio.mix_ready:window.seek(0);window.toggle_play();QTimer.singleShot(1200,finish_audio)
            elif window.hit_audio.audio_error or attempts[0]>=200:finish_audio()
            else:QTimer.singleShot(100,start_audio)
        QTimer.singleShot(100,start_audio)
    elif verify_regions:
        report=Path(sys.argv[2]).resolve();report.parent.mkdir(parents=True,exist_ok=True)
        def inspect_regions():
            window.load_region_draft(window.doc.regions[0]);window.stage.selected=0
            dialog=RegionDialog(window,0);dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen);dialog.resize(1400,880);dialog.show();dialog.zoom.setValue(1)
            for prop,a,b in [('center',[.5,.7],[.5,.3]),('angle',0,90),('width',1,.7),('height',.6,.4)]:
                dialog.store_event(prop,dict(start=1,end=4,**{'from':a,'to':b},ease='sine_in_out'))
            dialog.select_many((p,0) for p in dialog.PROPS);dialog.copy_selected();window.seek(8.123);dialog.paste_selected()
            pasted=len(dialog.selection)==4 and all(abs(dialog.track.events[p][1]['start']-8.123)<1e-8 for p in dialog.PROPS)
            dialog.delete_selected();dialog.undo();window.seek(2);dialog.select(('center',0))
            def capture_regions():
                dialog.grab().save(str(report.with_suffix('.png')))
                ok=pasted and all(len(dialog.track.events[p])==2 for p in dialog.PROPS) and dialog.doc.chart()['version']==6
                atomic_json(report,dict(ok=ok,frozen=bool(getattr(sys,'frozen',False)),lanes=list(dialog.PROPS),format=6,exactPaste=pasted,batchUndo=ok))
                dialog.reject();window.dirty=False;window.region_dirty=False;window.close();app.exit(0 if ok else 1)
            QTimer.singleShot(200,capture_regions)
        QTimer.singleShot(0,inspect_regions)
    elif verify_tracks:
        report=Path(sys.argv[2]).resolve();report.parent.mkdir(parents=True,exist_ok=True);window.output.setVolume(0)
        def inspect_tracks():
            dialog=TrackDialog(window);dialog.resize(1400,880);dialog.show();dialog.zoom.setValue(1)
            dialog.add_note(2);dialog.add_note(4,8)
            for prop,end,a,b,ease in [('x',8,.5,.8,1),('alpha',4,0,1,0),('speed',8,1,2,3)]:
                dialog.create_interval(prop,0,end);dialog.value_from.setValue(a*100 if prop=='x' else a);dialog.value_to.setValue(b*100 if prop=='x' else b);dialog.ease.setCurrentIndex(ease);dialog.write()
            window.seek(2);dialog.select(('x',0))
            def capture_tracks():
                dialog.grab().save(str(report.with_suffix('.png')))
                ok=len(dialog.doc.notes)==2 and dialog.doc.chart()['version']==6 and dialog.track.base('alpha')==0 and (_icons/'arrow-up.svg').is_file()
                atomic_json(report,dict(ok=ok,frozen=bool(getattr(sys,'frozen',False)),lanes=4,notes=len(dialog.doc.notes),format=dialog.doc.chart()['version'],defaults=[dialog.track.base('x'),dialog.track.base('alpha'),dialog.track.base('speed')]))
                dialog.reject();window.dirty=False;window.region_dirty=False;window.close();app.exit(0 if ok else 1)
            QTimer.singleShot(200,capture_tracks)
        QTimer.singleShot(0,inspect_tracks)
    elif verify:
        report=Path(sys.argv[2]).resolve();report.parent.mkdir(parents=True,exist_ok=True);window.output.setVolume(0)
        base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]));window.open_path(base/'app/src/main/assets/demo.json')
        attempts=[0]
        def finish_verify():
            ok=window.audio_loaded and window.player.position()>200 and len(window.doc.notes)==622
            window.player.pause();window.seek(9.5);window.timeline.ensure_beat(9.5)
            if verify_agent:
                from agent_client import skill_text
                window.load_region_draft(window.doc.regions[0]);window.stage.selected=0;window.tabs.setCurrentWidget(window.agent_panel);window.agent_panel.demo();window.seek(8)
                ok=ok and window.agent_panel.session is not None and window.agent_panel.session.changed() and 'interval-chart-agent' in skill_text()
            def capture():
                sound_ready=window.hit_audio.bank.ready();showcase=(base/'app/src/main/assets/at-flow.json').is_file();passed=ok and sound_ready and showcase and window.hit_audio.bank.played_count>0
                window.grab().save(str(report.with_suffix('.png')));atomic_json(report,dict(ok=passed,agent=verify_agent,notes=len(window.doc.notes),lines=len(window.doc.lines),format=window.doc.chart()['version'],audioLoaded=window.audio_loaded,decodedWaveBins=len(window.peaks),hitSoundsReady=sound_ready,hitSoundsPlayed=window.hit_audio.bank.played_count,showcaseAvailable=showcase,frozen=bool(getattr(sys,'frozen',False))));window.dirty=False;window.region_dirty=False;window.close();app.exit(0 if passed else 1)
            QTimer.singleShot(200,capture)
        def start_verify():
            attempts[0]+=1
            if window.audio_loaded and window.hit_audio.mix_ready:window.seek(6);window.toggle_play();QTimer.singleShot(1700,finish_verify)
            elif attempts[0]<100:QTimer.singleShot(100,start_verify)
            else:atomic_json(report,dict(ok=False,error='audio not ready'));app.exit(1)
        QTimer.singleShot(100,start_verify)
    elif len(sys.argv)>1:window.open_path(sys.argv[1])
    sys.exit(app.exec())

if __name__=='__main__':main()
