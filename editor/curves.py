"""Independent non-overlapping parameter intervals and exact speed integrals."""
from bisect import bisect_right
import math

EASES=('linear','sine_in_out','sine_in','sine_out','smooth','hold')
EASE_NAMES=('直线','Sin · 缓入缓出','Sin · 缓入','Sin · 缓出','平滑 S 型','保持起值，末端切换')

def eased(u,kind):
    if kind=='sine_in_out':return (1-math.cos(math.pi*u))/2
    if kind=='sine_in':return 1-math.cos(math.pi*u/2)
    if kind=='sine_out':return math.sin(math.pi*u/2)
    if kind=='smooth':return u*u*(3-2*u)
    if kind=='hold':return 0.
    return u

def ease_integral(u,kind):
    if kind=='sine_in_out':return u/2-math.sin(math.pi*u)/(2*math.pi)
    if kind=='sine_in':return u-2/math.pi*math.sin(math.pi*u/2)
    if kind=='sine_out':return 2/math.pi*(1-math.cos(math.pi*u/2))
    if kind=='smooth':return u**3-u**4/2
    if kind=='hold':return 0.
    return u*u/2

def validate_events(events,prop):
    if not isinstance(events,list) or len(events)>256:raise ValueError('每一栏最多 256 个变化区间')
    last=0.;maximum=8 if prop=='speed' else 1
    for event in events:
        if not isinstance(event,dict) or not all(type(event.get(k)) in (int,float) and math.isfinite(event[k]) for k in ('start','end','from','to')):raise ValueError('变化区间需要有限的起止拍与起止值')
        if not 0<=event['start']<event['end']<=600000 or event['start']<last-1e-8:raise ValueError('同一栏的区间不能重叠，且终点必须晚于起点')
        if not all(0<=event[k]<=maximum for k in ('from','to')):raise ValueError(f'{prop} 起止值必须在 0–{maximum} 之间')
        if event.get('ease','linear') not in EASES:raise ValueError('不支持的变化类型')
        last=event['end']

class Curve:
    def __init__(self,base,events):
        self.base=base;self.events=events;self.starts=[e['start'] for e in events];self.prefix=[]
        total=0.;at=0.;value=base
        for e in events:
            total+=(e['start']-at)*value;self.prefix.append(total)
            total+=self.area(e,1.);at=e['end'];value=e['to']
    @staticmethod
    def area(e,u):return (e['end']-e['start'])*(e['from']*u+(e['to']-e['from'])*ease_integral(u,e.get('ease','linear')))
    def value(self,time):
        i=bisect_right(self.starts,time)-1
        if i<0:return self.base
        e=self.events[i]
        if time>=e['end']:return e['to']
        return e['from']+(e['to']-e['from'])*eased((time-e['start'])/(e['end']-e['start']),e.get('ease','linear'))
    def primitive(self,time):
        i=bisect_right(self.starts,time)-1
        if i<0:return time*self.base
        e=self.events[i]
        if time>=e['end']:return self.prefix[i]+self.area(e,1)+(time-e['end'])*e['to']
        return self.prefix[i]+self.area(e,(time-e['start'])/(e['end']-e['start']))
    def distance(self,start,end):return self.primitive(end)-self.primitive(start)
    def time_at_distance(self,now,distance,limit):
        if not self.events:return min(limit,now+distance/self.base) if distance>=0 else max(limit,now+distance/self.base)
        target=self.primitive(now)+distance
        lo,hi=(now,limit) if distance>=0 else (limit,now)
        if target>=self.primitive(hi):return hi
        if target<=self.primitive(lo):return lo
        for _ in range(32):
            middle=(lo+hi)/2
            if self.primitive(middle)<target:lo=middle
            else:hi=middle
        return (lo+hi)/2
