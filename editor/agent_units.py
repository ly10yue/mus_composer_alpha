"""Convert only spatial Agent arguments/results, never opacity, beats or degrees."""
import copy
from versioning import scale_spatial,values

def arguments(name,args):
    a=copy.deepcopy(args)
    if name=='animate_region':
        for key in ('start_rect','end_rect'):a[key]=[v*.01 for v in a[key]]
    elif name=='set_region':scale_spatial({'regions':[a]},.01,True)
    elif name=='set_track':scale_spatial({'lines':[a]},.01)
    elif name=='set_track_events' and a['channel']=='x':
        for e in a['events']:values(e,.01)
    elif name=='set_region_center' or (name=='set_region_events' and a['channel'] in ('width','height')):
        for e in a['events']:values(e,.01)
    return a

def result(name,result):
    r=copy.deepcopy(result)
    if name=='get_track':scale_spatial({'lines':[r]},100)
    elif name=='list_regions':scale_spatial(r,100,True)
    elif name=='get_region':
        row=dict(rects=[r['rect']],motions=[r['frames']],events=[r['events']]);scale_spatial({'regions':[row]},100,True)
        r.update(rect=row['rects'][0],frames=row['motions'][0],events=row['events'][0])
    return r
