"""Independent rectangle channels, in beats in projects and seconds in charts."""
import math
from curves import Curve,EASES

PROPS=('center','angle','width','height')
LABELS=('中心点位置 X / Y','旋转角度 °','总长（横向）','总宽（纵向）')

def validate_channel(events,prop):
    if prop not in PROPS or not isinstance(events,list) or len(events)>256:raise ValueError('区域每栏最多 256 个时间条')
    last=0.
    for e in events:
        if not isinstance(e,dict) or not all(type(e.get(k)) in (int,float) and math.isfinite(e[k]) for k in ('start','end')):raise ValueError('区域时间条起止拍无效')
        if not 0<=e['start']<e['end']<=600000 or e['start']<last-1e-8:raise ValueError('同栏时间条不能重叠，终点需晚于起点')
        for key in ('from','to'):
            value=e.get(key);values=value if prop=='center' else [value]
            if not isinstance(values,list) or len(values)!=(2 if prop=='center' else 1):raise ValueError('中心点须为 [X,Y]')
            low,high=(-2,3) if prop=='center' else (-36000,36000) if prop=='angle' else (.001,4)
            if not all(type(v) in (int,float) and math.isfinite(v) and low<=v<=high for v in values):raise ValueError(f'{prop} 数值须在 {low}–{high} 内')
        if e.get('ease','linear') not in EASES:raise ValueError('区域变化类型无效')
        last=e['end']

def validate_region_events(events,count):
    if not isinstance(events,list) or (events and len(events)!=count):raise ValueError('区域时间条列表必须与矩形一一对应')
    for channels in events:
        if not isinstance(channels,dict):raise ValueError('区域通道必须为对象')
        for prop,items in channels.items():validate_channel(items,prop)

class RegionChannels:
    def __init__(self,rect,frames,events):self.rect=rect;self.frames=frames;self.events=events;self._curves={}
    def invalidate(self):self._curves.clear()
    def base(self,prop):
        l,t,r,b=self.rect;f=self.frames[0] if self.frames else dict(x=0,y=0,angle=0)
        return {'center':[(l+r)/2+f['x'],(t+b)/2+f['y']],'angle':f['angle'],'width':r-l,'height':b-t}[prop]
    def segments(self,prop):
        if prop in self.events:return self.events[prop]
        if prop in ('width','height'):return []
        l,t,r,b=self.rect
        def value(f):return [(l+r)/2+f['x'],(t+b)/2+f['y']] if prop=='center' else f['angle']
        return [dict(start=a['beat'],end=b['beat'],**{'from':value(a),'to':value(b)},ease=a.get('ease','linear')) for a,b in zip(self.frames,self.frames[1:])]
    def value(self,prop,beat):
        # Channel objects live for a paint / editing session; invalidated on edits.
        if prop not in self._curves:
            events=self.segments(prop);base=self.base(prop)
            self._curves[prop]=[Curve(base[i],[dict(e,**{'from':e['from'][i],'to':e['to'][i]}) for e in events]) for i in range(2)] if prop=='center' else Curve(base,events)
        curve=self._curves[prop]
        return [c.value(beat) for c in curve] if prop=='center' else curve.value(beat)

def transform(rect,frames,events,beat):
    channel=RegionChannels(rect,frames,events)
    return (*channel.value('center',beat),channel.value('angle',beat),channel.value('width',beat),channel.value('height',beat))

def scale_events(events,unit):
    return [{prop:[dict(e,start=round(e['start']*unit,8),end=round(e['end']*unit,8)) for e in items] for prop,items in channels.items()} for channels in events]
