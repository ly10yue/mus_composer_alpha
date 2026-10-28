"""The embedded agent's only editing surface. Every call validates and rolls back on error."""
from dataclasses import asdict
import copy
import hashlib
import json
import math
import re
from model import Document, Note, validate_rects
from tracks import Track, validate_tracks
from motion import validate_motions
from curves import validate_events,EASES
from region_events import validate_channel
import agent_units
from versioning import APP_VERSION

def obj(**properties):return dict(type='object',properties=properties,required=list(properties),additionalProperties=False)
def num(low=-600000,high=600000):return dict(type='number',minimum=low,maximum=high)
def integer(low=0,high=20000):return dict(type='integer',minimum=low,maximum=high)
def array(items,maximum,minimum=0):return dict(type='array',items=items,minItems=minimum,maxItems=maximum)
def string(maximum=120):return dict(type='string',maxLength=maximum)
BEAT=num(0,600000);EASE=dict(type='string',enum=['linear','smooth','hold'])
RECT=array(num(0,100),4,4)
AREA_KEY=obj(beat=BEAT,x=num(-200,200),y=num(-200,200),angle=num(-36000,36000),ease=EASE)
LINE_KEY=obj(beat=BEAT,x=num(0,100),alpha=num(0,1),ease=EASE)
EVENT_EASE=dict(type='string',enum=list(EASES))
EVENT=obj(start=BEAT,end=BEAT,**{'from':num(-36000,36000),'to':num(-36000,36000)},ease=EVENT_EASE)
CENTER_EVENT=obj(start=BEAT,end=BEAT,**{'from':array(num(-200,300),2,2),'to':array(num(-200,300),2,2)},ease=EVENT_EASE)
LINE_ID=dict(type='string',pattern=r'^[A-Za-z0-9_-]{1,64}$',maxLength=64)
NOTE_ID=dict(type=['integer','null'],minimum=0,maximum=1000000000)

def tool(name,description,parameters):return dict(type='function',function=dict(name=name,description=description,strict=True,parameters=parameters))
TOOLS=[
    tool('get_context','读取当前草稿概况、BPM、小节换算、原始选择和轨迹列表。音频与本机路径不提供。',obj()),
    tool('list_regions','分页列出当前草稿的区域段落及矩形；任何分段修改后，索引可能改变，应重新查询。',obj(offset=integer(0,5000),limit=integer(1,32))),
    tool('get_region','读取某段中某个矩形及其完整运动关键帧；索引均从 0 开始。',obj(region_index=integer(0,4999),rect_index=integer(0,31))),
    tool('get_notes','分页读取头部位于 [start_beat,end_beat) 的音符。返回 ID、拍数、轨迹、持续拍。',obj(start_beat=BEAT,end_beat=BEAT,offset=integer(),limit=integer(1,200))),
    tool('get_track','读取指定轨迹的全部关键帧，修改前用它保留未要求更改的帧。',obj(line_id=LINE_ID)),
    tool('animate_region','在所选段落内部的 [start_beat,end_beat) 修改一个矩形的平移/旋转。保留其他矩形与范围外内容。起止矩形可用不同尺寸实现缩放。跨已有段落时改用 set_region 明确替换范围。',
         obj(region_index=integer(0,4999),rect_index=integer(0,31),start_beat=BEAT,end_beat=BEAT,start_rect=RECT,end_rect=RECT,start_angle=num(-36000,36000),end_angle=num(-36000,36000),ease=EASE)),
    tool('set_region','显式替换 [start_beat,end_beat) 内的整组矩形和运动；范围外内容保留。motions=[] 表示全静态，否则与 rects 对应。谨慎使用，区间内旧内容会被替换。',
         obj(start_beat=BEAT,end_beat=BEAT,label=string(80),rects=array(RECT,32),motions=array(array(AREA_KEY,256),32))),
    tool('set_track','新增轨迹或替换指定轨迹的全部关键帧。现有音符绑定 ID 不变。只支持横向位置和线透明度。',obj(line_id=LINE_ID,name=string(80),frames=array(LINE_KEY,256,1))),
    tool('set_track_events','替换指定轨迹的一栏时间条，其他栏和绑定音符保留。先 get_track 保留该栏未修改的条目。x 为 0–100，alpha 为 0–1，speed 为 0–8；events=[] 固定初始值。',obj(line_id=LINE_ID,channel=dict(type='string',enum=['x','alpha','speed']),events=array(EVENT,256))),
    tool('delete_track','删除无音符绑定的线。至少保留一条线，且仅在用户要求删除时调用。',obj(line_id=LINE_ID)),
    tool('set_region_center','替换某矩形的中心点栏时间条；from/to 为绝对 [X,Y]。先 get_region 读取并保留未修改的时间条，其他栏不变。',obj(region_index=integer(0,4999),rect_index=integer(0,31),events=array(CENTER_EVENT,256))),
    tool('set_region_events','替换某矩形的一栏时间条，其他栏不变。angle 是顺时针度数 ±36000；width/height 为总长/总宽 0.1–400（全屏为 100）。先 get_region 保留未修改条目。',obj(region_index=integer(0,4999),rect_index=integer(0,31),channel=dict(type='string',enum=['angle','width','height']),events=array(EVENT,256))),
    tool('edit_notes','批量新建或修改音符：id=null 新建，否则修改已有 ID；length=0 为 Tap，>0 为 Hold。拍数精确保存，不自动吸附网格。',
         obj(notes=array(obj(id=NOTE_ID,beat=BEAT,line=LINE_ID,length=BEAT),1000,1))),
    tool('delete_notes','删除明确指定的已有音符 ID；只有用户要求删除时调用。',obj(ids=array(integer(0,1000000000),1000,1))),
    tool('validate_chart','检查当前草稿可玩性，包括区域可触及性、重叠、音频关联。检查错误不授权修改未请求的音符。',obj())
]
SCHEMAS={t['function']['name']:t['function']['parameters'] for t in TOOLS}
READ_TOOLS={'get_context','list_regions','get_region','get_notes','get_track','validate_chart'}

def validate_schema(value,schema,path='arguments'):
    kind=schema['type'];kinds=kind if isinstance(kind,list) else [kind]
    valid=any((k=='null' and value is None) or (k=='object' and isinstance(value,dict)) or
              (k=='array' and isinstance(value,list)) or (k=='string' and isinstance(value,str)) or
              (k=='integer' and type(value) is int) or (k=='number' and type(value) in (int,float) and math.isfinite(value)) for k in kinds)
    if not valid:raise ValueError(f'{path}: 类型错误，要求 {kind}')
    if value is None:return
    if 'enum' in schema and value not in schema['enum']:raise ValueError(f'{path}: 不支持的枚举值')
    if isinstance(value,dict):
        if set(value)!=set(schema['properties']):raise ValueError(f'{path}: 必须且只能包含 {", ".join(schema["properties"])}')
        for key,child in schema['properties'].items():validate_schema(value[key],child,path+'.'+key)
    elif isinstance(value,list):
        if not schema.get('minItems',0)<=len(value)<=schema.get('maxItems',1000):raise ValueError(f'{path}: 数组长度超限')
        for i,child in enumerate(value):validate_schema(child,schema['items'],f'{path}[{i}]')
    elif isinstance(value,str):
        if len(value)>schema.get('maxLength',10000) or ('pattern' in schema and not re.fullmatch(schema['pattern'],value)):raise ValueError(f'{path}: 字符串长度或格式错误')
    elif type(value) in (int,float):
        if not math.isfinite(value) or not schema.get('minimum',-math.inf)<=value<=schema.get('maximum',math.inf):raise ValueError(f'{path}: 数值超限')

def fingerprint(doc):return hashlib.sha256(json.dumps(doc.project(),sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()

class EditSession:
    def __init__(self,doc,selection=None,cursor=0.,target=None):
        self.original=copy.deepcopy(doc);self.doc=copy.deepcopy(doc);self.base_hash=fingerprint(doc)
        self.selection=sorted(selection or []);self.cursor=cursor;self.target=copy.deepcopy(target);self.operations=[];self.preview_start=cursor;self.preview_end=min(doc.end_beat,cursor+doc.meter*2)

    def context(self):
        d=self.doc;target=copy.deepcopy(self.target)
        if target and target.get('rect'):target['rect']=[v*100 for v in target['rect']]
        return dict(appVersion=APP_VERSION,coordinateScale=100,title=d.title,bpm=d.bpm,meter=d.meter,offset_seconds=d.offset,duration_seconds=d.duration,end_beat=d.end_beat,
                    cursor_beat=self.cursor,grid_step=d.step,selected_note_ids=self.selection[:1000],selection_truncated=len(self.selection)>1000,
                    original_selected_region=target,note_count=len(d.notes),region_count=len(d.regions),
                    lines=[dict(id=t.id,name=t.name,frame_count=len(t.frames),event_counts={k:len(v) for k,v in t.events.items()},pose_at_cursor=[t.pose(self.cursor)[0]*100,t.pose(self.cursor)[1]]) for t in d.lines],
                    conventions='小节从 1 开始；绝对拍从 0 开始；第 N 小节开头=(N-1)*meter。区间左闭右开。屏幕坐标 0–100；x 向右、y 向下，矩形为 [left,top,right,bottom]。')

    def call(self,name,args):
        if name not in SCHEMAS:raise ValueError('工具不在允许列表中')
        validate_schema(args,SCHEMAS[name]);before=copy.deepcopy(self.doc);old_preview=(self.preview_start,self.preview_end)
        try:
            result=self._dispatch(name,agent_units.arguments(name,args))
            if name not in READ_TOOLS:
                # Parser-level constraints; playability issues remain visible for review.
                Document.from_project(self.doc.project())
                self.operations.append(dict(tool=name,arguments=copy.deepcopy(args)))
            return agent_units.result(name,result)
        except Exception:
            self.doc=before;self.preview_start,self.preview_end=old_preview;raise

    def _range(self,a):
        start,end=a['start_beat'],a['end_beat']
        if not 0<=start<end<=self.doc.end_beat+1e-5:raise ValueError('起止拍必须在谱面范围内且起点小于终点')
        return start,end

    def _region(self,index):
        if index>=len(self.doc.regions):raise ValueError('区域索引不存在，请重新 list_regions')
        return self.doc.regions[index]

    def _dispatch(self,name,a):
        d=self.doc
        if name=='get_context':return self.context()
        if name=='list_regions':
            rows=[dict(index=i,start=r.start,end=r.end,label=r.label,rects=r.rects,motion_counts=[len(fs) for fs in r.motions]) for i,r in enumerate(d.regions)]
            return dict(total=len(rows),regions=rows[a['offset']:a['offset']+a['limit']])
        if name=='get_region':
            r=self._region(a['region_index']);i=a['rect_index']
            if i>=len(r.rects):raise ValueError('矩形索引不存在')
            return dict(region_index=a['region_index'],rect_index=i,start=r.start,end=r.end,label=r.label,rect=r.rects[i],frames=r.motions[i] if r.motions else [],events=r.events[i] if r.events else {})
        if name=='get_notes':
            self._range(a);notes=[asdict(n) for n in sorted(d.notes,key=lambda n:n.beat) if a['start_beat']<=n.beat<a['end_beat']]
            return dict(total=len(notes),notes=notes[a['offset']:a['offset']+a['limit']])
        if name=='get_track':
            if a['line_id'] not in {t.id for t in d.lines}:raise ValueError('轨迹不存在')
            return asdict(d.track(a['line_id']))
        if name=='animate_region':
            start,end=self._range(a);r=self._region(a['region_index']);i=a['rect_index']
            if i>=len(r.rects):raise ValueError('矩形索引不存在')
            if start<r.start-1e-7 or end>r.end+1e-7:raise ValueError('运动范围超出所选段落；请逐段编辑或用 set_region 显式替换区间')
            first,last=a['start_rect'],a['end_rect'];validate_rects([first,last])
            events=copy.deepcopy(r.events) or [{} for _ in r.rects];events[i]={}
            for prop,dimension in [('width',2),('height',3)]:
                begin=first[dimension]-first[dimension-2];finish=last[dimension]-last[dimension-2]
                if abs(begin-finish)>1e-7:events[i][prop]=[dict(start=start,end=end,**{'from':begin,'to':finish},ease=a['ease'])]
            rects=copy.deepcopy(r.rects);motions=copy.deepcopy(r.motions) or [[] for _ in rects];rects[i]=first
            motions[i]=[dict(beat=start,x=0.,y=0.,angle=a['start_angle'],ease=a['ease']),
                        dict(beat=end,x=(last[0]+last[2]-first[0]-first[2])/2,y=(last[1]+last[3]-first[1]-first[3])/2,angle=a['end_angle'],ease='linear')]
            d.set_region(start,end,rects,r.label,motions,events,r.names);self.preview_start,self.preview_end=start,end
            return dict(changed=True,start_beat=start,end_beat=end,rect_index=i,notice='范围外原状态保留；终点属于后一段，预览结束前一瞬可看运动终态。请重新查询段落索引。')
        if name=='set_region':
            start,end=self._range(a);d.set_region(start,end,a['rects'],a['label'],a['motions']);self.preview_start,self.preview_end=start,end
            return dict(changed=True,region_count=len(d.regions),notice='范围内整组矩形已替换，请重新查询段落索引')
        if name=='set_track':
            old=next((t for t in d.lines if t.id==a['line_id']),None)
            events={'speed':copy.deepcopy(old.events['speed'])} if old and 'speed' in old.events else {}
            line=Track(a['line_id'],a['name'],copy.deepcopy(a['frames']),events);d.lines=[line if t.id==line.id else t for t in d.lines] if any(t.id==line.id for t in d.lines) else d.lines+[line];validate_tracks(d.lines)
            self.preview_start=line.frames[0]['beat'];self.preview_end=min(d.end_beat,max(self.preview_start+d.meter,line.frames[-1]['beat']))
            return dict(changed=True,line_id=line.id,frames=len(line.frames))
        if name=='set_track_events':
            track=d.track(a['line_id']);prop=a['channel'];validate_events(a['events'],prop)
            track.events[prop]=copy.deepcopy(a['events']);track.invalidate()
            return dict(changed=True,line_id=track.id,channel=prop,count=len(a['events']))
        if name=='delete_track':
            d.track(a['line_id'])
            if len(d.lines)<=1 or any(n.line==a['line_id'] for n in d.notes):raise ValueError('至少保留一条线；绑定音符的线不能删除')
            d.lines=[t for t in d.lines if t.id!=a['line_id']];return dict(deleted=True)
        if name in ('set_region_center','set_region_events'):
            r=self._region(a['region_index']);i=a['rect_index'];prop='center' if name=='set_region_center' else a['channel']
            if i>=len(r.rects):raise ValueError('矩形索引不存在')
            validate_channel(a['events'],prop)
            if not r.events:r.events=[{} for _ in r.rects]
            r.events[i][prop]=copy.deepcopy(a['events']);self.preview_start=r.start;self.preview_end=r.end
            return dict(changed=True,region_index=a['region_index'],rect_index=i,channel=prop)
        if name=='edit_notes':
            ids=[n['id'] for n in a['notes'] if n['id'] is not None]
            if len(set(ids))!=len(ids):raise ValueError('一次请求不能多次修改同一音符')
            by_id={n.id:n for n in d.notes};next_id=max(by_id,default=-1)+1;changed=[]
            for n in a['notes']:
                if n['line'] not in {t.id for t in d.lines}:raise ValueError('音符引用的轨迹不存在')
                if d.seconds(n['beat'])+d.offset<0 or d.seconds(n['beat']+n['length'])+d.offset>d.duration:raise ValueError('音符超出歌曲时长')
                if n['id'] is not None and n['id'] not in by_id:raise ValueError('音符 ID 不存在')
                note_id=next_id if n['id'] is None else n['id']
                if n['id'] is None:next_id+=1
                by_id[note_id]=Note(note_id,n['beat'],n['line'],n['length']);changed.append(note_id)
            d.notes=sorted(by_id.values(),key=lambda n:(n.beat,n.id));self.preview_start=min(n['beat'] for n in a['notes']);self.preview_end=min(d.end_beat,max(n['beat']+n['length'] for n in a['notes'])+d.meter)
            return dict(changed_ids=changed)
        if name=='delete_notes':
            ids=set(a['ids'])
            if not ids<={n.id for n in d.notes}:raise ValueError('包含不存在的音符 ID')
            d.notes=[n for n in d.notes if n.id not in ids];return dict(deleted=len(ids))
        if name=='validate_chart':return self.validation()
        raise ValueError('工具未实现')

    def validation(self):
        errors,warnings=self.doc.validate()
        return dict(error_count=len(errors),warning_count=len(warnings),errors=errors[:20],warnings=warnings[:20])

    def changed(self):return fingerprint(self.doc)!=self.base_hash

    def summary(self):
        return dict(operations=len(self.operations),notes_before=len(self.original.notes),notes_after=len(self.doc.notes),
                    regions_before=len(self.original.regions),regions_after=len(self.doc.regions),lines_before=len(self.original.lines),lines_after=len(self.doc.lines))
