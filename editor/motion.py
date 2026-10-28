"""Region keyframes and geometry. Matches Engine.Zone in the Android runtime."""
import math

EASINGS = ('linear', 'smooth', 'hold')
ASPECTS = ((1066.6666667-96)/600, (800-96)/600)

def validate_motions(motions, count):
    if not isinstance(motions,list) or (motions and len(motions)!=count):
        raise ValueError('区域运动列表必须与矩形一一对应')
    for frames in motions:
        if not isinstance(frames,list) or len(frames)>256:raise ValueError('每个矩形最多 256 个关键帧')
        previous=-1.
        for f in frames:
            if not isinstance(f,dict) or not all(isinstance(f.get(k),(int,float)) and math.isfinite(f[k]) for k in ('beat','x','y','angle')):
                raise ValueError('关键帧必须包含有限的拍数、位移和角度')
            if not 0<=f['beat']<=600000 or f['beat']<=previous or abs(f['x'])>2 or abs(f['y'])>2 or abs(f['angle'])>36000 or f.get('ease','linear') not in EASINGS:
                raise ValueError('关键帧拍数需递增且非负；位移 ±2、角度 ±36000，缓动类型必须有效')
            previous=f['beat']

def pose(frames, beat):
    if not frames:return 0.,0.,0.
    a=frames[0]
    if beat<=a['beat']:return a['x'],a['y'],a['angle']
    for b in frames[1:]:
        if beat<b['beat']:
            u=(beat-a['beat'])/(b['beat']-a['beat'])
            ease=a.get('ease','linear')
            if ease=='smooth':u=u*u*(3-2*u)
            elif ease=='hold':u=0.
            return tuple(a[k]+(b[k]-a[k])*u for k in ('x','y','angle'))
        a=b
    return a['x'],a['y'],a['angle']

def polygon(rect, frames, beat, aspect, events=None):
    from region_events import transform
    if events:cx,cy,angle,width,height=transform(rect,frames,events,beat)
    else:
        l,t,r,b=rect;dx,dy,angle=pose(frames,beat);cx,cy,width,height=(l+r)/2+dx,(t+b)/2+dy,r-l,b-t
    l,t,r,b=cx-width/2,cy-height/2,cx+width/2,cy+height/2
    dx=dy=0.;a=math.radians(angle);c=math.cos(a);s=math.sin(a)
    return [(cx+dx+(c*(x-cx)*aspect-s*(y-cy))/aspect,
             cy+dy+s*(x-cx)*aspect+c*(y-cy)) for x,y in ((l,t),(r,t),(r,b),(l,b))]

def touch_y(rect, frames, beat, aspect, x, events=None):
    """Intersection of a transformed rectangle with a vertical note column and screen."""
    if not 0<=x<=1:return None
    points=polygon(rect,frames,beat,aspect,events);ys=[]
    for (ax,ay),(bx,by) in zip(points,points[1:]+points[:1]):
        if min(ax,bx)-1e-7<=x<=max(ax,bx)+1e-7:
            if abs(bx-ax)<1e-9:
                if abs(x-ax)<1e-7:ys.extend((ay,by))
            else:ys.append(ay+(by-ay)*(x-ax)/(bx-ax))
    if not ys:return None
    lo=max(0.,min(ys));hi=min(1.,max(ys))
    return (lo+hi)/2 if lo<=hi+1e-7 else None

def reachable(region,beat,x,aspect):
    return any(touch_y(rect,region.motions[i] if region.motions else [],beat,aspect,x,region.events[i] if region.events else {}) is not None
               for i,rect in enumerate(region.rects))
