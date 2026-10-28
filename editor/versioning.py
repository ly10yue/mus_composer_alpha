"""Public 0–100 coordinates; the geometry engine keeps normalized units internally."""
import copy
APP_VERSION='0.12.0'
FORMAT_VERSION=6
MIN_READER='0.12.0'

def metadata():return dict(version=FORMAT_VERSION,appVersion=APP_VERSION,minReaderVersion=MIN_READER,coordinateScale=100)

def values(event,factor):
    for key in ('from','to'):
        v=event[key];event[key]=[round(x*factor,12) for x in v] if isinstance(v,list) else round(v*factor,12)

def scale_spatial(data,factor,project=False):
    for line in data.get('lines',[]):
        for f in line.get('frames',[]):f['x']=round(f['x']*factor,12)
        for e in line.get('events',{}).get('x',[]):values(e,factor)
    for n in data.get('notes',[]):
        if 'x' in n:n['x']=round(n['x']*factor,12)
    for region in data.get('regions' if project else 'sections',[]):
        region['rects']=[[round(v*factor,12) for v in rect] for rect in region['rects']]
        for frames in region.get('motions',[]):
            for f in frames:f['x']=round(f['x']*factor,12);f['y']=round(f['y']*factor,12)
        for channels in region.get('events',[]):
            for prop,events in channels.items():
                if prop in ('center','width','height'):
                    for e in events:values(e,factor)
    return data

def encode(data,project=False):
    data=copy.deepcopy(data)
    scale_spatial(data['document'] if project else data,100,project)
    data.update(metadata());return data

def decode(data,project=False):
    data=copy.deepcopy(data);version=data.get('version')
    if type(version) is not int or not 1<=version<=FORMAT_VERSION:raise ValueError('此文件格式需要更新的制谱器')
    if version==6:
        if data.get('coordinateScale')!=100:raise ValueError('v6 文件必须声明 coordinateScale=100')
        minimum=data.get('minReaderVersion')
        try:parts=tuple(int(x) for x in minimum.split('.'));current=tuple(map(int,APP_VERSION.split('.')))
        except (AttributeError,ValueError):raise ValueError('缺少或无效的 minReaderVersion')
        if len(parts)!=3 or min(parts)<0 or parts>current:raise ValueError('此谱面要求较新的版本：'+minimum)
        scale_spatial(data['document'] if project else data,.01,project)
        data['version']=5
    elif data.get('coordinateScale',1)!=1:raise ValueError('旧格式必须使用 0–1 坐标，不能按数值大小猜测单位')
    return data

def display_factor(prop):return 100 if prop in ('x','center','width','height') else 1
