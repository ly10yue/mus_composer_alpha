"""Track shapes scroll vertically; each absolute beat keeps its own x coordinate."""
from dataclasses import dataclass, field
import math
import re
from bisect import bisect_right
from curves import Curve,validate_events

@dataclass
class Track:
    id: str
    name: str
    frames: list[dict] = field(default_factory=list)
    events: dict = field(default_factory=dict)

    def legacy_pose(self, beat):
        if getattr(self,'_frame_source',None) is not self.frames or len(getattr(self,'_frame_times',()))!=len(self.frames):
            self._frame_source=self.frames;self._frame_times=[f['beat'] for f in self.frames]
        index=bisect_right(self._frame_times,beat)-1
        if index<0:return self.frames[0]['x'],self.frames[0]['alpha']
        a=self.frames[index]
        if index==len(self.frames)-1:return a['x'],a['alpha']
        b=self.frames[index+1];u=(beat-a['beat'])/(b['beat']-a['beat'])
        if a.get('ease')=='smooth':u=u*u*(3-2*u)
        elif a.get('ease')=='hold':u=0
        return a['x']+(b['x']-a['x'])*u,a['alpha']+(b['alpha']-a['alpha'])*u

    def base(self,prop):return 1. if prop=='speed' else self.frames[0][prop]
    def segments(self,prop):
        if prop in self.events:return self.events[prop]
        if prop=='speed':return []
        return [dict(start=a['beat'],end=b['beat'],**{'from':a[prop],'to':b[prop]},ease=a.get('ease','linear')) for a,b in zip(self.frames,self.frames[1:])]
    def channel(self,prop):
        source=self.events.get(prop);base=self.base(prop);cache=getattr(self,'_curves',{})
        item=cache.get(prop)
        if item is None or item[0] is not source or item[1]!=base:
            item=(source,base,Curve(base,source or []));cache[prop]=item;self._curves=cache
        return item[2]
    def value(self,prop,beat):
        if prop!='speed' and prop not in self.events:return self.legacy_pose(beat)[0 if prop=='x' else 1]
        return self.channel(prop).value(beat)
    def pose(self,beat):
        x,alpha=self.legacy_pose(beat)
        return self.channel('x').value(beat) if 'x' in self.events else x,self.channel('alpha').value(beat) if 'alpha' in self.events else alpha
    def distance(self,now,arrival):return self.channel('speed').distance(now,arrival)
    def horizon(self,now,distance,limit):return self.channel('speed').time_at_distance(now,distance,limit)
    def invalidate(self):self._curves={};self._frame_source=None

    def x_at(self, now, arrival):
        # `now` only affects screen y. A point never slides sideways while falling.
        return self.pose(arrival)[0]

    def samples(self, now, start, end, step):
        if end < start:return []
        count = max(1, min(512, math.ceil((end-start)/step)))
        times = {start+(end-start)*i/count for i in range(count+1)}
        for i,f in enumerate(self.frames):
            at = f['beat']
            if start < at <= end:
                times.add(at)
                # The incoming segment can hold its old position until this beat.
                if i and self.frames[i-1].get('ease')=='hold':
                    times.add(max(start,at-1e-7))
        for prop in ('x','speed'):
            for e in self.events.get(prop,[]):
                for at in (e['start'],e['end']):
                    if start<at<=end:times.add(at);times.add(max(start,at-1e-7))
        return [(s,self.x_at(now,s)) for s in sorted(times)]

def defaults():
    return [Track(f'line{i+1}',f'轨迹 {i+1}',[dict(beat=0.,x=x,alpha=1.,ease='linear')])
            for i,x in enumerate((.18,.39,.61,.82))]

def validate_tracks(lines):
    if not 1 <= len(lines) <= 64:raise ValueError('谱面需要 1–64 条轨迹线')
    ids=set();count=0
    for line in lines:
        if not isinstance(line.id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',line.id) or line.id in ids:
            raise ValueError('轨迹 ID 必须唯一，只能包含字母、数字、下划线和连字符')
        ids.add(line.id)
        if not isinstance(line.name,str) or not 1<=len(line.frames)<=256:raise ValueError('每条轨迹需要 1–256 个关键帧')
        last=-1
        for f in line.frames:
            if not all(isinstance(f.get(k),(int,float)) and math.isfinite(f[k]) for k in ('beat','x','alpha')):
                raise ValueError('轨迹关键帧需要有限数字')
            if not 0<=f['beat']<=600000 or f['beat']<=last or not 0<=f['x']<=1 or not 0<=f['alpha']<=1 or f.get('ease','linear') not in ('linear','smooth','hold'):
                raise ValueError('轨迹帧时间必须递增，位置和透明度在 0–1 之间')
            last=f['beat']
        count+=len(line.frames)
        if not isinstance(line.events,dict) or set(line.events)-{'x','alpha','speed'}:raise ValueError('轨迹变化栏只能为位置、透明度、流速')
        for prop,events in line.events.items():validate_events(events,prop);count+=len(events)
    if count>16384:raise ValueError('轨迹关键帧数量超限')
