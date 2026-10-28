"""Shared clipboard transactions and detented navigation for authoring canvases."""
import copy,json,math
from PySide6.QtWidgets import QApplication
from model import Note
from versioning import APP_VERSION,display_factor,values

PREFIX='INTERVAL_TIMELINE_V1\n'

def write_clipboard(kind,items):
    if not items:return
    items=copy.deepcopy(items)
    for i in items:
        if i['prop']!='notes':values(i['data'],display_factor(i['prop']))
    QApplication.clipboard().setText(PREFIX+json.dumps(dict(kind=kind,items=items,appVersion=APP_VERSION,coordinateScale=100),allow_nan=False))

def read_clipboard():
    text=QApplication.clipboard().text()
    if not text.startswith(PREFIX):return None
    raw=text[len(PREFIX):]
    if len(raw)>4*1024*1024:raise ValueError('剪贴板内容过大')
    result=json.loads(raw)
    if not isinstance(result,dict) or result.get('kind') not in ('notes','track','region') or not isinstance(result.get('items'),list) or len(result['items'])>20000:raise ValueError('无效谱面剪贴板')
    scale=result.get('coordinateScale',1)
    if scale not in (1,100):raise ValueError('不支持的剪贴板坐标单位')
    if scale==100:
        for i in result['items']:
            if i['prop']!='notes':values(i['data'],1/display_factor(i['prop']))
    return result

def shifted_items(items,anchor):
    if not items:return []
    # Preserve original spacing, including off-grid starts. Do not quantize a paste.
    first=min(i['data']['beat'] if i['prop']=='notes' else i['data']['start'] for i in items)
    result=copy.deepcopy(items)
    for i in result:
        keys=('beat',) if i['prop']=='notes' else ('start','end')
        for key in keys:i['data'][key]=round(i['data'][key]+anchor-first,9)
    return result

def append_notes(doc,items,line=None):
    notes=[];ident=max((n.id for n in doc.notes),default=-1)+1
    occupied={(n.line,round(n.beat,7)) for n in doc.notes}
    for item in items:
        n=item['data'];beat=n['beat'];length=n['length'];binding=line or n['line']
        if not all(type(v) in (int,float) and math.isfinite(v) for v in (beat,length)) or not 0<=beat<=beat+length<=doc.end_beat:raise ValueError('粘贴音符超出谱面范围')
        if binding not in {t.id for t in doc.lines}:raise ValueError('粘贴音符引用的线不存在')
        key=(binding,round(beat,7))
        if key in occupied:raise ValueError('粘贴位置已有同线音符；本次未写入，请移动游标')
        occupied.add(key);notes.append(Note(ident,beat,binding,length));ident+=1
    if len(doc.notes)+len(notes)>20000:raise ValueError('全谱最多 20000 音符')
    return notes

class GridWheel:
    def __init__(self):self.remainder=0.;self.grid=None
    def steps(self,event,grid):
        if self.grid!=grid:self.remainder=0.;self.grid=grid
        # Angle deltas are platform-independent (120 per notch). Accumulate high-resolution wheels.
        delta=event.angleDelta().y()/120 if event.angleDelta().y() else event.pixelDelta().y()/40
        if delta*self.remainder<0:self.remainder=0.
        self.remainder+=delta;steps=math.trunc(self.remainder);self.remainder-=steps
        return steps

class BatchTimelineEdits:
    clipboard_kind='track'
    def select_many(self,keys):
        keys=set(keys);self.select(next(iter(keys)) if len(keys)==1 else None);self.selection=keys
        self.delete_button.setEnabled(bool(keys))
        if len(keys)>1:self.selection_label.setText(f'已框选 {len(keys)} 项 · Ctrl+C 复制 / Delete 删除')
        self.timeline.viewport().update()
    def copy_selected(self):
        from dataclasses import asdict
        selected=getattr(self,'selection',set())
        items=[dict(prop=key[0],data=asdict(data) if key[0]=='notes' else copy.deepcopy(data)) for key,start,end,data in self.timeline.items() if key in selected]
        write_clipboard(self.clipboard_kind,items);self.hint.setText(f'已复制 {len(items)} 项；粘贴将最早起点对齐当前判定线。')
    def paste_selected(self):
        try:
            clip=read_clipboard()
            if not clip:return
            if clip['kind']!=self.clipboard_kind and not (clip['kind']=='notes' and self.clipboard_kind=='track'):raise ValueError('线与区域的时间条不能混贴')
            items=shifted_items(clip['items'],self.cursor);events={};new_notes=[]
            for item in items:
                prop=item['prop'];data=item['data']
                if prop not in self.PROPS:raise ValueError('剪贴板栏目不匹配')
                if prop=='notes':continue
                if not 0<=data['start']<data['end']<=self.doc.end_beat:raise ValueError('粘贴时间条超出谱面范围')
                events.setdefault(prop,copy.deepcopy(self.track.segments(prop))).append(data)
            for prop,values in events.items():values.sort(key=lambda e:e['start']);self.validate_channel(values,prop)
            if any(i['prop']=='notes' for i in items):new_notes=append_notes(self.doc,[i for i in items if i['prop']=='notes'],self.track.id)
        except (ValueError,TypeError,KeyError) as ex:self.hint.setText(str(ex));return
        if not items:return
        self.checkpoint();self.doc.notes.extend(new_notes);self.track.events.update(events);self.track.invalidate();self.changed()
        selected={('notes',n.id) for n in new_notes}
        selected.update((i['prop'],self.track.segments(i['prop']).index(i['data'])) for i in items if i['prop']!='notes')
        self.select_many(selected);self.hint.setText(f'已粘贴 {len(selected)} 项；起点 {self.cursor:g} 拍，可整体撤销。')
    def delete_selected(self):
        selected=getattr(self,'selection',set())
        if not selected:return
        self.checkpoint();ids={i for prop,i in selected if prop=='notes'};self.doc.notes=[n for n in self.doc.notes if n.id not in ids]
        for prop in self.PROPS:
            if prop=='notes':continue
            indices={i for p,i in selected if p==prop}
            if indices:self.track.events[prop]=[e for i,e in enumerate(self.track.segments(prop)) if i not in indices]
        self.track.invalidate();self.changed();self.select(None)
