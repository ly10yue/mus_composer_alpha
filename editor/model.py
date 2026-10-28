"""Beat-based editor model; emits the same v3 seconds-based chart the game reads."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import copy
import json
import math
import os
import tempfile
import zipfile
from motion import validate_motions, reachable, ASPECTS
from tracks import Track, defaults, validate_tracks
from region_events import validate_region_events,scale_events
from versioning import encode,decode

DIVISIONS = (1, 2, 3, 4, 6, 8, 12, 16, 24, 32)
FULL = [[0., 0., 1., 1.]]
MAX_PACKAGE = 256 * 1024 * 1024

@dataclass
class Note:
    id: int
    beat: float
    line: str
    length: float = 0.

@dataclass
class Region:
    start: float
    end: float
    label: str = '全域'
    rects: list[list[float]] = field(default_factory=lambda: copy.deepcopy(FULL))
    motions: list[list[dict]] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    names: list[str] = field(default_factory=list)

@dataclass
class Document:
    title: str = 'Untitled'
    artist: str = ''
    difficulty: str = 'CUSTOM'
    bpm: float = 120.
    meter: int = 4
    offset: float = 0.
    duration: float = 60.
    audio: str = ''
    division: int = 4
    grid_unit: str = 'beat'
    notes: list[Note] = field(default_factory=list)
    regions: list[Region] = field(default_factory=list)
    lines: list[Track] = field(default_factory=defaults)

    def __post_init__(self):
        if not self.regions:
            self.regions = [Region(0, self.end_beat)]

    @property
    def end_beat(self):
        return max(1., (self.duration - self.offset + 3) * self.bpm / 60)

    def seconds(self, beat):
        return beat * 60 / self.bpm

    def snap(self, beat):
        return max(0., math.floor(beat / self.step + .5) * self.step)

    @property
    def step(self):
        return (self.meter if self.grid_unit=='bar' else 1) / self.division

    def region_at(self, beat):
        return next((r for r in self.regions if r.start <= beat < r.end), None)

    def track(self, line_id):
        return next(t for t in self.lines if t.id==line_id)

    def line_for_x(self, x):
        # Legacy callers/imports acquire one shared static line per coordinate.
        for line in self.lines:
            if len(line.frames)==1 and abs(line.frames[0]['x']-x)<1e-6:return line.id
        if len(self.lines)>=64:raise ValueError('最多支持 64 条轨迹线')
        line_id=self.new_line_id();self.lines.append(Track(line_id,line_id,[dict(beat=0.,x=x,alpha=1.,ease='linear')]))
        return line_id

    def new_line_id(self):
        i=1
        while any(t.id==f'line{i}' for t in self.lines):i+=1
        return f'line{i}'

    def note_x(self, note, now=None, arrival=None):
        # Every segment has a fixed x; time advances only its screen y.
        at=note.beat if arrival is None or not note.length else max(note.beat,min(note.beat+note.length,arrival))
        return self.track(note.line).pose(at)[0]

    def nearest_line(self, x, now, arrival):
        return min(self.lines,key=lambda t:abs(t.x_at(now,arrival)-x)).id

    def add(self, beat, line, length=0.):
        beat = self.snap(beat)
        if isinstance(line,(int,float)):line=self.line_for_x(max(0.,min(1.,line)))
        self.track(line)
        if any(abs(n.beat-beat)<1e-7 and n.line==line for n in self.notes):return None
        n=Note(max((n.id for n in self.notes),default=-1)+1,beat,line,length)
        self.notes.append(n)
        return n

    def fill(self,start,end,line,length=0.):
        start=self.snap(start);end=self.snap(end)
        if not all(math.isfinite(v) for v in (start,end,length)) or end<=start or length<0:
            raise ValueError('填充范围或音符参数无效')
        if length>self.step+1e-7:
            raise ValueError('Hold 长度不能大于网格间距，否则会同列重叠')
        count=math.ceil((end-start)/self.step-1e-8)
        if count>2000 or len(self.notes)+count>20000:
            raise ValueError('单次最多填充 2000 个音符，谱面最多 20000 个')
        if self.seconds(start)+self.offset<0 or self.seconds(start+(count-1)*self.step+length)+self.offset>self.duration:
            raise ValueError('填充范围超出歌曲时长')
        result=[]
        for i in range(count):
            n=self.add(start+i*self.step,line,length)
            if n:result.append(n.id)
        return result

    def set_region(self, start, end, rects, label, motions=None, events=None, names=None):
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= self.end_beat + .00001):
            raise ValueError('区域起止拍必须满足 0 ≤ 起点 < 终点 ≤ 谱面结束拍')
        validate_rects(rects)
        motions=motions or [];validate_motions(motions,len(rects))
        events=events or [];validate_region_events(events,len(rects))
        result = []
        for r in self.regions:
            if r.end <= start or r.start >= end:
                result.append(copy.deepcopy(r))
            else:
                if r.start < start:
                    result.append(Region(r.start, start, r.label, copy.deepcopy(r.rects),copy.deepcopy(r.motions),copy.deepcopy(r.events),copy.deepcopy(r.names)))
                if r.end > end:
                    result.append(Region(end, r.end, r.label, copy.deepcopy(r.rects),copy.deepcopy(r.motions),copy.deepcopy(r.events),copy.deepcopy(r.names)))
        result.append(Region(start, end, label or '自定义区域', copy.deepcopy(rects),copy.deepcopy(motions),copy.deepcopy(events),copy.deepcopy(names or [])))
        self.regions = sorted(result, key=lambda r: r.start)

    def retime(self, bpm, keep_beats=True):
        if not math.isfinite(bpm) or not 20 <= bpm <= 400:
            raise ValueError('BPM 必须在 20–400 之间')
        ratio = bpm / self.bpm
        if not keep_beats:
            for n in self.notes:
                n.beat *= ratio
                n.length *= ratio
            for line in self.lines:
                for f in line.frames:f['beat']*=ratio
                for events in line.events.values():
                    for event in events:event['start']*=ratio;event['end']*=ratio
                line.invalidate()
            for r in self.regions:
                r.start *= ratio
                r.end *= ratio
                for frames in r.motions:
                    for f in frames:f['beat']*=ratio
                r.events=scale_events(r.events,ratio)
        self.bpm = bpm
        self.fit_regions()

    def fit_regions(self):
        end = self.end_beat
        self.regions = [r for r in self.regions if r.start < end]
        if not self.regions:
            self.regions = [Region(0, end)]
        self.regions[-1].end = end
        self.regions = [r for r in self.regions if r.start < r.end]

    def validate(self):
        errors, warnings = [], []
        if not self.audio or not Path(self.audio).is_file():
            errors.append('未导入歌曲或歌曲文件不存在。')
        if not self.notes:
            warnings.append('谱面还没有音符。')
        try:validate_tracks(self.lines)
        except ValueError as ex:return [str(ex)],warnings
        previous = 0.;invalid_regions=False;frame_count=0
        for r in self.regions:
            if abs(r.start - previous) > 1e-5 or r.end <= r.start:
                errors.append('区域时间轴不连续或存在重叠。')
            try:
                validate_rects(r.rects);validate_motions(r.motions,len(r.rects));validate_region_events(r.events,len(r.rects))
            except ValueError as ex:
                errors.append(str(ex));invalid_regions=True
            if not invalid_regions:frame_count+=sum(len(frames) for frames in r.motions)+sum(len(es) for channels in r.events for es in channels.values())
            previous = r.end
        if not self.regions or previous < self.end_beat - 1e-5:
            errors.append('区域时间轴未覆盖歌曲末尾。')
        if frame_count>20000:errors.append('全谱最多支持 20000 个区域关键帧。')
        if invalid_regions:return errors,warnings
        sorted_notes = sorted(self.notes, key=lambda n: n.beat)
        for i, n in enumerate(sorted_notes):
            if not all(math.isfinite(v) for v in (n.beat, n.length)) or not 0<=n.beat<=600000 or not 0<=n.length<=600000 or n.line not in {t.id for t in self.lines}:
                errors.append(f'音符 {n.id} 数据无效。')
                continue
            start, end = self.seconds(n.beat) + self.offset, self.seconds(n.beat+n.length) + self.offset
            if start < 0 or end > self.duration:
                errors.append(f'音符 {n.id} 超出歌曲时长（第 {n.beat:g} 拍）。');continue
            region = self.region_at(n.beat)
            if region is None or not all(reachable(region,n.beat,self.note_x(n),aspect) for aspect in ASPECTS):
                errors.append(f'音符 {n.id} 在 16:9 或 4:3 下不在开放区域的横向范围内。')
            if n.length:
                if len(self.track(n.line).frames)>1:
                    warnings.append(f'Hold {n.id} 随轨迹弯折并竖直下落，持续判定时请跟随下方交点。')
                samples=min(4096,max(2,math.ceil(n.length*8)))
                times={n.beat+n.length*j/samples for j in range(1,samples+1)}
                times.update(r.start for r in self.regions if n.beat<r.start<n.beat+n.length)
                for at in sorted(times):
                    r=self.region_at(at)
                    if r is None or not all(reachable(r,at,self.note_x(n,arrival=at),a) for a in ASPECTS):
                        errors.append(f'Hold {n.id} 的轨迹在第 {at:g} 拍离开开放区域。');break
            if n.length and any(any(r.motions) for r in self.regions if r.end>n.beat and r.start<n.beat+n.length):
                warnings.append(f'Hold {n.id} 经过运动区域，请检查移动过程及持续可触及性。')
            if n.length and any(n.beat < r.start < n.beat+n.length for r in self.regions):
                warnings.append(f'Hold {n.id} 跨越区域切换，请检查能否持续按住。')
            for p in sorted_notes[i+1:]:
                if (n.length and p.beat >= n.beat+n.length-1e-7) or p.beat > n.beat + max(n.length, .0001):
                    break
                if p.line not in {t.id for t in self.lines}:continue
                if abs(self.note_x(p)-self.note_x(n,arrival=p.beat)) < .085:
                    errors.append(f'音符 {n.id} 与 {p.id} 同列重叠。')
            active = sum(p.beat <= n.beat < p.beat + max(p.length, .00001) for p in sorted_notes)
            if active > 2:
                warnings.append(f'第 {n.beat:g} 拍需要超过两根手指。')
        return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))

    def format_version(self):return 5 if any(any(r.events) for r in self.regions) else 4 if any(t.events for t in self.lines) else 3

    def chart(self, audio_name=None):
        result=dict(version=self.format_version(), title=self.title, artist=self.artist, difficulty=self.difficulty,
                    bpm=self.bpm, audio=audio_name or Path(self.audio).name, duration=self.duration,
                    offset=self.offset, approachTime=2.2,
                    editor=dict(meter=self.meter, division=self.division,gridUnit=self.grid_unit),
                    lines=[export_line(t,60/self.bpm) for t in self.lines],
                    notes=[dict(id=i, type='hold' if n.length else 'tap', time=round(self.seconds(n.beat), 8),
                                line=n.line, duration=round(self.seconds(n.length), 8))
                           for i,n in enumerate(sorted(self.notes, key=lambda n: (n.beat, n.line)))],
                    sections=[dict(start=round(self.seconds(r.start), 8), end=round(self.seconds(r.end), 8),
                                   label=r.label, rects=r.rects, names=r.names, **(dict(events=scale_events(r.events,60/self.bpm)) if any(r.events) else {}), **(dict(motions=[[dict(time=round(self.seconds(f['beat']),8),x=f['x'],y=f['y'],angle=f['angle'],ease=f.get('ease','linear')) for f in frames] for frames in r.motions]) if any(r.motions) else {})) for r in self.regions])

        return encode(result)

    def project(self):
        data=asdict(self)
        for r in data['regions']:
            if not any(r['motions']):r.pop('motions')
            if not any(r['events']):r.pop('events')
        for line in data['lines']:
            if not line['events']:line.pop('events')
        return encode(dict(format='interval-project', version=self.format_version(), document=data),True)

    @classmethod
    def from_project(cls, data, base=None):
        data=decode(data,True)
        if data.get('format') != 'interval-project' or data.get('version') not in (1,2,3,4,5):
            raise ValueError('不支持的工程文件')
        d = copy.deepcopy(data['document'])
        if data['version']<5 and any(any(r.get('events',[])) for r in d['regions']):raise ValueError('区域时间条需要 v5 工程')
        if data['version']<3:
            legacy=cls(lines=[])
            for n in d['notes']:n['line']=legacy.line_for_x(n.pop('x'))
            d['lines']=[asdict(t) for t in (legacy.lines or defaults())]
        d['lines']=[Track(**t) for t in d['lines']];validate_tracks(d['lines'])
        d['notes'] = [Note(**n) for n in d['notes']]
        d['regions'] = [Region(**r) for r in d['regions']]
        doc = cls(**d)
        if not math.isfinite(doc.bpm) or not 20 <= doc.bpm <= 400 or not math.isfinite(doc.duration) or not 0 < doc.duration <= 86400 or not math.isfinite(doc.offset) or abs(doc.offset)>600 or doc.division not in DIVISIONS or not 1<=doc.meter<=16 or doc.grid_unit not in ('beat','bar'):
            raise ValueError('工程时间参数无效')
        if len(doc.notes)>20000 or len(doc.regions)>5000 or not doc.regions:
            raise ValueError('工程规模超出支持范围')
        ids=set()
        for n in doc.notes:
            if not isinstance(n.id,int) or n.id in ids or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in (n.beat,n.length)) or not 0<=n.beat<=600000 or not 0<=n.length<=600000 or n.line not in {t.id for t in doc.lines}:
                raise ValueError('工程音符数据无效')
            ids.add(n.id)
        previous=0.
        for r in doc.regions:
            if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in (r.start,r.end)) or abs(r.start-previous)>1e-4 or r.end<=r.start:
                raise ValueError('工程区域必须连续且不重叠')
            validate_rects(r.rects);validate_motions(r.motions,len(r.rects));validate_region_events(r.events,len(r.rects));previous=r.end
            if r.names and (len(r.names)!=len(r.rects) or any(not isinstance(n,str) or len(n)>80 for n in r.names)):raise ValueError('区域名称须与矩形对应，名称最多 80 字')
        if sum(sum(len(fs) for fs in r.motions)+sum(len(es) for ch in r.events for es in ch.values()) for r in doc.regions)>20000:raise ValueError('全谱最多 20000 个区域关键帧')
        if previous<doc.end_beat-1e-4:
            # Game charts may end immediately after the song; extend the last state for editor padding.
            if previous<(doc.duration-doc.offset)*doc.bpm/60-1e-4:raise ValueError('工程区域未覆盖歌曲')
            doc.regions[-1].end=doc.end_beat
        if base and doc.audio and not Path(doc.audio).is_absolute():
            doc.audio = str((Path(base)/doc.audio).resolve())
        return doc

    @classmethod
    def from_chart(cls, data, audio=''):
        data=decode(data)
        if data.get('version') not in (1,2,3,4,5):
            raise ValueError('仅支持 INTERVAL v1/v2/v3/v4/v5 JSON；PhiEdit / Phigros 原谱请先转换')
        if data['version']<5 and any(any(s.get('events',[])) for s in data['sections']):raise ValueError('区域时间条需要 v5 格式')
        if data['version']<4 and any(t.get('events') for t in data.get('lines',[])):raise ValueError('轨迹区间事件需要 v4 格式')
        if data.get('version')==1 and any(any(s.get('motions',[])) for s in data['sections']):raise ValueError('动画区域需要 v2 谱面')
        bpm = float(data['bpm'])
        if not math.isfinite(bpm) or not 20 <= bpm <= 400:
            raise ValueError('无效 BPM')
        unit = bpm/60
        ed = data.get('editor', {})
        notes=[];legacy=cls(lines=[])
        lines=[Track(t['id'],t.get('name',t['id']),[dict(beat=float(f['time'])*unit,x=f['x'],alpha=f['alpha'],ease=f.get('ease','linear')) for f in t['frames']],{prop:[dict(e,start=e['start']*unit,end=e['end']*unit) for e in events] for prop,events in t.get('events',{}).items()}) for t in data.get('lines',[])]
        if data['version']>=3:validate_tracks(lines)
        for i,n in enumerate(data['notes']):
            if n['type'] not in ('tap','hold'):
                raise ValueError('仅支持 Tap / Hold')
            duration=float(n.get('duration',0))
            if not math.isfinite(duration) or duration<0 or (n['type']=='hold' and duration<=0):raise ValueError('Hold 需要正的持续时间')
            line=n['line'] if data['version']>=3 else legacy.line_for_x(float(n['x']))
            notes.append(Note(i,float(n['time'])*unit,line,duration*unit if n['type']=='hold' else 0))
        if data['version']<3:lines=legacy.lines or defaults()
        doc=cls(lines=lines,title=data['title'], artist=data.get('artist',''), difficulty=data.get('difficulty','CUSTOM'),
                bpm=bpm, offset=float(data.get('offset',0)), duration=float(data['duration']), audio=audio,
                meter=ed.get('meter',4), division=ed.get('division',4),grid_unit=ed.get('gridUnit','beat'),notes=notes,
                regions=[Region(float(s['start'])*unit,float(s['end'])*unit,s.get('label','区域'),s['rects'],[[dict(beat=float(f['time'])*unit,x=f['x'],y=f['y'],angle=f['angle'],ease=f.get('ease','linear')) for f in frames] for frames in s.get('motions',[])],scale_events(s.get('events',[]),unit),s.get('names',[])) for s in data['sections']])
        # Reuse strict project header validation, retaining a missing-audio draft.
        doc=cls.from_project(doc.project())
        for r in doc.regions:
            validate_rects(r.rects)
        return doc

def export_line(track,unit):
    result=dict(id=track.id,name=track.name,frames=[dict(time=round(f['beat']*unit,8),x=f['x'],alpha=f['alpha'],ease=f.get('ease','linear')) for f in track.frames])
    if track.events:result['events']={prop:[dict(e,start=round(e['start']*unit,8),end=round(e['end']*unit,8)) for e in events] for prop,events in track.events.items()}
    return result

def validate_rects(rects):
    if len(rects)>32:
        raise ValueError('每段最多支持 32 个矩形')
    for rect in rects:
        if len(rect)!=4 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in rect):
            raise ValueError('区域坐标必须为四个有限数字')
        l,t,r,b=rect
        if not 0<=l<r<=1 or not 0<=t<b<=1:
            raise ValueError('矩形坐标必须在 0–1 内，且左 < 右、上 < 下')

def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('w',encoding='utf-8') as file:
        json.dump(value,file,ensure_ascii=False,indent=2,allow_nan=False)
        file.flush();os.fsync(file.fileno())
    os.replace(temporary,path)

def export_package(doc, path):
    errors,_=doc.validate()
    if errors:
        raise ValueError('\n'.join(errors[:12]))
    audio=Path(doc.audio)
    if audio.stat().st_size>MAX_PACKAGE:
        raise ValueError('歌曲文件超过 256 MB')
    name='music'+audio.suffix.lower()
    path=Path(path);temporary=path.with_name(path.name+'.tmp')
    try:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as z:
            chart_json=json.dumps(doc.chart(name),ensure_ascii=False,allow_nan=False)
            if len(chart_json.encode('utf-8'))>4*1024*1024:raise ValueError('谱面 JSON 超过 4 MB')
            z.writestr('chart.json',chart_json)
            z.write(audio,name)
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)

def import_package(path, folder):
    """Extract only chart.json and its single basename audio entry; never extractall."""
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path) as z:
        infos=z.infolist()
        if len(infos)>8 or sum(i.file_size for i in infos)>MAX_PACKAGE+4*1024*1024:
            raise ValueError('谱面包过大')
        if len({i.filename for i in infos})!=len(infos):
            raise ValueError('谱面包有重复文件')
        if z.getinfo('chart.json').file_size>4*1024*1024:
            raise ValueError('谱面 JSON 过大')
        data=json.loads(z.read('chart.json'))
        name=data['audio']
        if not isinstance(name,str) or '/' in name or '\\' in name or ':' in name or name in ('','.','..','chart.json'):
            raise ValueError('无效歌曲文件名')
        doc=Document.from_chart(data,str(folder/name))
        with z.open(name) as source,(folder/name).open('wb') as target:
            count=0
            while chunk:=source.read(65536):
                count+=len(chunk)
                if count>MAX_PACKAGE:
                    raise ValueError('歌曲文件过大')
                target.write(chunk)
        return doc

class History:
    def __init__(self):
        self.undo_stack=[];self.redo_stack=[]
    def push(self, doc):
        self.undo_stack.append(copy.deepcopy(doc));self.undo_stack=self.undo_stack[-100:];self.redo_stack.clear()
    def undo(self, doc):
        if not self.undo_stack:return doc
        self.redo_stack.append(copy.deepcopy(doc));return self.undo_stack.pop()
    def redo(self, doc):
        if not self.redo_stack:return doc
        self.undo_stack.append(copy.deepcopy(doc));return self.redo_stack.pop()
