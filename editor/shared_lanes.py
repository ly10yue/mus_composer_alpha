"""The main window's shared four-lane editor. Both canvases edit the same document."""
from lane_inspector import LaneInspector
from curves import validate_events
from region_events import RegionChannels,PROPS as REGION_PROPS,LABELS as REGION_LABELS,validate_channel
from timeline_edit import BatchTimelineEdits
from track_editor import TrackDialog,PROPS as TRACK_PROPS,LABELS as TRACK_LABELS
from region_editor import RegionDialog
from track_view import TrackTimeline


class Notice:
    def __init__(self,editor):self.editor=editor
    def setText(self,text):self.editor.statusBar().showMessage(text,5000)


class SharedLanes(BatchTimelineEdits):
    cache_lane_items=True
    def __init__(self,editor,targets):
        self.editor=editor;self.targets=targets;self.region_mode=False
        self.index=0;self.indices={False:0,True:0};self.selected=None;self.selection=set();self.section=None
        self.hint=Notice(editor);self.timeline=TrackTimeline(self)
        self.panel=LaneInspector(self);self.name=self.panel.name
        targets.currentIndexChanged.connect(self.choose)
        self.refresh()

    @property
    def doc(self):return self.editor.doc
    @property
    def cursor(self):return self.editor.cursor
    @property
    def tool(self):return self.editor.tool
    @property
    def zoom(self):return self.editor.scroll_speed
    @property
    def PROPS(self):return REGION_PROPS if self.region_mode else TRACK_PROPS
    @property
    def LABELS(self):return REGION_LABELS if self.region_mode else TRACK_LABELS
    @property
    def clipboard_kind(self):return 'region' if self.region_mode else 'track'
    @property
    def region(self):return self.doc.region_at(self.cursor) or self.doc.regions[-1]
    @property
    def track(self):
        if not self.region_mode:return self.doc.lines[self.index]
        r=self.region;i=self.index
        return RegionChannels(r.rects[i] if r.rects else [0,0,1,1],r.motions[i] if r.motions else [],r.events[i] if r.events else {})

    def choose(self,index):
        if index<0:return
        self.index=index;self.timeline.sync();self.panel.target_name();self.select(None)
        if self.region_mode:self.editor.agent_panel.refresh_target()

    def refresh(self):
        r=self.region;self.section=r
        names=([f'{r.label} / '+(r.names[i] if r.names else f'区域 {i+1}') for i in range(len(r.rects))]
               if self.region_mode else [t.name for t in self.doc.lines])
        self.index=max(0,min(self.index,len(names)-1));self.targets.blockSignals(True)
        self.targets.clear();self.targets.addItems(names);self.targets.setCurrentIndex(self.index);self.targets.blockSignals(False)
        self.timeline.setEnabled(bool(names));self.timeline.ppb=self.editor.timeline.ppb;self.timeline.sync()
        self.panel.objects();self.select(None)

    def switch(self,region):
        self.indices[self.region_mode]=self.index
        self.region_mode=region;self.index=self.indices[region];self.timeline.edge.stop();self.timeline.drag=None;self.timeline.marquee=None
        self.refresh()
        for mode,b in enumerate(self.editor.mode_buttons):b.setChecked(bool(mode)==region)
        self.timeline.setFocus()

    def follow(self):
        if self.region_mode and self.section is not self.region:self.refresh()
        self.timeline.ensure_beat(self.cursor)
    def pause(self):self.editor.hit_audio.pause()
    def checkpoint(self):
        self.pause();self.editor.checkpoint()
        if self.region_mode and not self.region.events:self.region.events=[{} for _ in self.region.rects]
    def changed(self):
        self.editor.selection.intersection_update(n.id for n in self.doc.notes)
        self.editor.changed()
    def select(self,key):
        self.selected=key;self.selection={key} if key else set();self.timeline.viewport().update();self.panel.selection()
    def select_many(self,keys):
        self.selection=set(keys);self.selected=next(iter(self.selection)) if len(self.selection)==1 else None
        self.timeline.viewport().update();self.panel.selection()
    def paste_selected(self):
        if self.timeline.isEnabled():super().paste_selected()
    def validate_channel(self,items,prop):
        (validate_channel if self.region_mode else validate_events)(items,prop)
    def store_event(self,prop,event,replace=None):
        method=RegionDialog.store_event if self.region_mode else TrackDialog.store_event
        ok=method(self,prop,event,replace)
        if ok:self.hint.setText('已更新 '+self.LABELS[self.PROPS.index(prop)]+' · Ctrl+Z 撤销')
        return ok
    create_interval=TrackDialog.create_interval
    add_note=TrackDialog.add_note
    update_note=TrackDialog.update_note

    def selected_item(self):
        return next(data for key,_,__,data in self.timeline.items() if key==self.selected)

    def edit_item(self,key):
        self.pause();self.select(key)
        box=self.panel.start if key[0]=='notes' else self.panel.values[0]
        box.setFocus();box.selectAll()

    def add_target(self):
        (RegionDialog.add_line if self.region_mode else TrackDialog.add_line)(self)

    def remove_target(self):
        (RegionDialog.delete_line if self.region_mode else TrackDialog.delete_line)(self)

    def rename_target(self,value):
        if not value or not self.targets.count():self.panel.target_name();return
        if self.region_mode:
            r=self.region
            names=r.names or [f'区域 {i+1}' for i in range(len(r.rects))]
            if names[self.index]==value:return
            self.checkpoint();r.names=list(names);r.names[self.index]=value
        else:
            if self.track.name==value:return
            self.checkpoint();self.track.name=value
        self.changed()
