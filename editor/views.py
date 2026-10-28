"""Editor canvases: beat grid, rectangle authoring, and game-space preview."""
import copy
import math
from motion import polygon
from model import Note
from timeline_edit import GridWheel
from edge_pan import EdgePan
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QPolygonF, QPainterPath,QTransform
from PySide6.QtWidgets import QAbstractScrollArea, QWidget

BG=QColor('#10191b');PANEL=QColor('#182527');MINT=QColor('#a6f4cf');ORANGE=QColor('#ffb682');INK=QColor('#edf5eb');MUTED=QColor('#8da5a4');GRID=QColor('#304244')

class Timeline(QAbstractScrollArea):
    def __init__(self, window):
        super().__init__();self.window=window;self.ppb=64.;self.ruler=84;self._note_shapes={};self.wheel=GridWheel();self.edge=EdgePan(self)
        self.setMinimumWidth(420);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().setMouseTracking(True);self.drag=None;self.marquee=None
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.verticalScrollBar().valueChanged.connect(self.scrub)
        self.sync()
    @property
    def doc(self):return self.window.doc
    def sync(self):
        self._note_shapes.clear()
        bar=self.verticalScrollBar();bar.blockSignals(True)
        bar.setRange(0,round(self.doc.end_beat*1000))
        bar.setSingleStep(max(1,round(self.doc.step*1000)))
        bar.setPageStep(max(1,round(self.viewport().height()/self.ppb*1000)))
        bar.setValue(round(self.window.cursor*1000));bar.blockSignals(False);self.viewport().update()
    def resizeEvent(self,event):super().resizeEvent(event);self.sync()
    def scrollContentsBy(self,dx,dy):self.viewport().update()
    def judgement_y(self):return self.viewport().height()*.8
    def beat_y(self,beat):return self.judgement_y()-(beat-self.window.cursor)*self.ppb
    def y_beat(self,y):return self.window.cursor+(self.judgement_y()-y)/self.ppb
    def scrub(self,value):
        if self.window.playing():self.window.toggle_play()
        self.window.seek(value/1000)
    def x_at(self,x):return self.ruler+x*(self.viewport().width()-self.ruler-20)
    def at_x(self,x):return max(0,min(1,(x-self.ruler)/(self.viewport().width()-self.ruler-20)))
    def snap_x(self,x):return round(x,4)
    def note_shape(self,n):
        key=(n.id,n.beat,n.length,n.line,self.ppb,self.viewport().width())
        shape=self._note_shapes.get(key)
        if shape is None:
            if not n.length:
                x=self.x_at(self.doc.note_x(n,self.window.cursor));y=-n.beat*self.ppb
                shape=QPolygonF([QPointF(x-23,y-6),QPointF(x+23,y-6),QPointF(x+23,y+6),QPointF(x-23,y+6)])
            else:
                points=self.doc.track(n.line).samples(self.window.cursor,n.beat,n.beat+n.length,max(.02,4/self.ppb))
                shape=QPolygonF([QPointF(self.x_at(x)-23,-b*self.ppb) for b,x in points]+[QPointF(self.x_at(x)+23,-b*self.ppb) for b,x in reversed(points)])
            if len(self._note_shapes)>4096:self._note_shapes.clear()
            self._note_shapes[key]=shape
        return QTransform().translate(0,self.judgement_y()+self.window.cursor*self.ppb).map(shape)
    def note_rect(self,n):return self.note_shape(n).boundingRect().adjusted(0,-6,0,6)
    def hit(self,pos):
        return next((n for n in reversed(self.doc.notes) if self.note_shape(n).containsPoint(pos,Qt.FillRule.OddEvenFill) or (abs(pos.y()-self.beat_y(n.beat+n.length))<9 and abs(pos.x()-self.x_at(self.doc.note_x(n,self.window.cursor,n.beat+n.length)))<27)),None)
    def ensure_beat(self,beat):
        # Time navigation moves the chart, never the judgement line.
        bar=self.verticalScrollBar();bar.blockSignals(True);bar.setValue(round(beat*1000));bar.blockSignals(False)
        self.viewport().update()
    def paintEvent(self,event):
        p=QPainter(self.viewport());p.setRenderHint(QPainter.RenderHint.Antialiasing);p.fillRect(self.viewport().rect(),BG)
        width=self.viewport().width();height=self.viewport().height();p.setFont(QFont('Consolas',9))
        first=max(0,self.y_beat(height)-1);last=min(self.doc.end_beat,self.y_beat(27)+1)
        p.fillRect(QRectF(0,self.judgement_y(),width,height-self.judgement_y()),QColor('#0c1416'))
        for r in self.doc.regions:
            if r.end<first or r.start>last:continue
            y=self.beat_y(r.start);end=self.beat_y(r.end)
            p.fillRect(QRectF(width-16,end,10,y-end),QColor('#40695b') if r.rects else QColor('#805340'))
            p.setPen(MINT);p.drawLine(QPointF(width-19,y),QPointF(width,y))
        step=self.doc.step
        if self.ppb*step>=5:
            p.setPen(QColor('#203033'))
            for i in range(int(first/step),math.ceil(last/step)+1):
                y=self.beat_y(i*step);p.drawLine(QPointF(self.ruler,y),QPointF(width-20,y))
        for beat in range(int(first),math.ceil(last)+1):
            y=self.beat_y(beat);bar=beat%self.doc.meter==0
            p.setPen(QPen(QColor('#56766e') if bar else GRID,1.5 if bar else 1))
            p.drawLine(QPointF(self.ruler,y),QPointF(width-20,y))
            p.setPen(MINT if bar else MUTED);p.drawText(QRectF(7,y-10,73,20),Qt.AlignmentFlag.AlignRight,f'{int(beat)//self.doc.meter+1:03d} : {int(beat)%self.doc.meter+1}')
        labels=[];selected_lines={n.line for n in self.doc.notes if n.id in self.window.selection}
        for track in self.doc.lines:
            points=track.samples(self.window.cursor,max(0,self.y_beat(height)),max(0,self.y_beat(27)),4/self.ppb)
            color=QColor(MINT);color.setAlpha(round(track.pose(self.window.cursor)[1]*100));p.setPen(QPen(color,1.5))
            p.drawPolyline(QPolygonF([QPointF(self.x_at(x),self.beat_y(b)) for b,x in points]))
            x=self.x_at(track.pose(self.window.cursor)[0]);p.drawEllipse(QPointF(x,self.judgement_y()),4,4)
            alpha=track.pose(self.window.cursor)[1]
            if alpha>=.5 or track.id in selected_lines:labels.append((track.id not in selected_lines,-alpha,x,track.name))
        occupied=[[],[]];p.setPen(MUTED)
        for _,_,x,name in sorted(labels):
            left=max(self.ruler,min(width-100,x-35))
            for row in range(2):
                if all(abs(left-other)>=82 for other in occupied[row]):
                    occupied[row].append(left);text=p.fontMetrics().elidedText(name,Qt.TextElideMode.ElideRight,78)
                    p.drawText(QPointF(left,self.judgement_y()+30+row*18),text);break
        # The same song envelope is shown alongside the beat ruler.
        if self.window.peaks:
            p.setPen(QColor('#42665b'))
            for y in range(0,height,3):
                t=self.doc.seconds(self.y_beat(y))+self.doc.offset;idx=int(t*50)
                if 0<=idx<len(self.window.peaks):
                    amp=self.window.peaks[idx]*22;p.drawLine(QPointF(self.ruler+amp,y),QPointF(self.ruler,y))
        preview={}
        if self.drag and self.drag['kind'] in ('move','tail'):
            selected=[n for n in self.doc.notes if n.id in self.window.selection]
            if selected:
                db=self.drag['last'][0]-self.drag['start'][0];dx=self.drag['last'][1]-self.drag['start'][1]
                db=max(db,-min(n.beat for n in selected))
                for n in selected:
                    clone=copy.copy(n)
                    if self.drag['kind']=='tail':
                        if n.id==self.drag['note']:clone.length=max(self.doc.step,self.doc.snap(n.beat+n.length+db)-n.beat)
                    else:
                        clone.beat+=db
                        if abs(dx)>.01:clone.line=self.doc.nearest_line(self.doc.note_x(n,self.window.cursor)+dx,self.window.cursor,clone.beat)
                    preview[n.id]=clone
        for original in self.doc.notes:
            n=preview.get(original.id,original)
            if n.beat+n.length<first or n.beat>last:continue
            r=self.note_rect(n);selected=n.id in self.window.selection
            p.setPen(QPen(INK if selected else (ORANGE if n.length else MINT),2 if selected else 1))
            p.setBrush(QColor('#705a40') if n.length else MINT);p.drawPolygon(self.note_shape(n))
            for at in ([n.beat,n.beat+n.length] if n.length else [n.beat]):
                x=self.x_at(self.doc.note_x(n,self.window.cursor,at));y=self.beat_y(at)
                p.fillRect(QRectF(x-24,y-4,48,8),ORANGE if n.length else MINT)
            if selected:
                p.setPen(INK);p.drawText(QRectF(r.right()+5,r.y()-4,90,20),f'{n.beat:g}')
        if self.drag and self.drag['kind']=='hold':
            a=self.drag['start'];b=self.drag['last'];n=Note(-1,min(a[0],b[0]),self.drag['line'],max(self.doc.step,abs(b[0]-a[0])))
            p.setPen(ORANGE);p.setBrush(QColor(255,182,130,70));p.drawPolygon(self.note_shape(n))
        if self.marquee:
            p.setBrush(QColor(166,244,207,30));p.setPen(MINT);p.drawRect(self.marquee.normalized())
        y=self.judgement_y();p.setPen(QPen(ORANGE,2));p.drawLine(QPointF(0,y),QPointF(width,y))
        p.fillRect(QRectF(0,y-24,self.ruler-4,48),PANEL);p.setPen(ORANGE);p.drawText(8,round(y-6),'判定线');p.drawText(8,round(y+16),f'{self.window.cursor:.2f}')
        p.fillRect(QRectF(0,0,width,27),PANEL);p.setPen(MUTED);p.drawText(10,18,'小节 : 拍');unit='小节' if self.doc.grid_unit=='bar' else '拍';p.drawText(self.ruler+16,18,f'{self.window.tool.upper()}    /    1/{self.doc.division} {unit}    /    {len(self.doc.notes)} NOTES')
        p.end()
    def mousePressEvent(self,event):
        self.setFocus();pos=event.position()
        if pos.y()<27 or pos.x()>self.viewport().width()-20:return
        if self.window.playing():self.window.toggle_play()
        n=self.hit(pos)
        if event.button()==Qt.MouseButton.RightButton:
            if n:self.window.checkpoint();self.doc.notes.remove(n);self.window.selection.discard(n.id);self.window.changed()
            return
        if event.button()!=Qt.MouseButton.LeftButton:return
        if pos.x()<self.ruler:
            self.window.seek(self.doc.snap(self.y_beat(pos.y())));return
        raw_beat=self.y_beat(pos.y())
        if raw_beat<-.00001:return
        beat=self.doc.snap(raw_beat);x=self.snap_x(self.at_x(pos.x()))
        if beat>self.doc.end_beat:return
        if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier|Qt.KeyboardModifier.ControlModifier):
            self.marquee=QRectF(pos,pos);self.drag={'kind':'box','origin':pos};self.edge.begin(pos);return
        if self.window.tool=='tap':
            self.window.checkpoint();added=self.doc.add(beat,self.window.placement_line(x,beat))
            if added:self.window.selection={added.id};self.window.changed()
        elif self.window.tool=='hold':self.drag={'kind':'hold','start':(beat,x),'last':(beat,x),'line':self.window.placement_line(x,beat)}
        else:
            if n:
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    if n.id in self.window.selection:self.window.selection.remove(n.id)
                    else:self.window.selection.add(n.id)
                elif n.id not in self.window.selection:self.window.selection={n.id}
                tail=n.length and abs(pos.y()-self.beat_y(n.beat+n.length))<10
                self.drag={'kind':'tail' if tail else 'move','note':n.id,'start':(beat,x),'last':(beat,x)}
            else:self.window.selection.clear();self.window.seek(beat)
            self.window.selection_changed()
        self.viewport().update()
    def mouseMoveEvent(self,event):
        if not self.drag:return
        pos=event.position();self.drag['last']=(self.doc.snap(self.y_beat(pos.y())),self.snap_x(self.at_x(pos.x())))
        if self.drag['kind']=='box':self.edge.move(pos)
        self.viewport().update()
    def mouseReleaseEvent(self,event):
        if not self.drag:return
        drag=self.drag;self.drag=None;self.edge.stop()
        if drag['kind']=='box':
            r=self.marquee.normalized();self.window.selection={n.id for n in self.doc.notes if r.intersects(self.note_rect(n))};self.marquee=None;self.window.selection_changed()
        elif drag['kind']=='hold':
            a,x=drag['start'];b=drag['last'][0];length=max(self.doc.step,abs(b-a));self.window.checkpoint();n=self.doc.add(min(a,b),drag['line'],length)
            if n:self.window.selection={n.id};self.window.changed()
        else:
            db=drag['last'][0]-drag['start'][0];dx=drag['last'][1]-drag['start'][1]
            selected=[n for n in self.doc.notes if n.id in self.window.selection]
            if selected and (abs(db)>.00001 or abs(dx)>.00001):
                self.window.checkpoint()
                if drag['kind']=='tail':
                    n=next(n for n in self.doc.notes if n.id==drag['note']);n.length=max(self.doc.step,self.doc.snap(n.beat+n.length+db)-n.beat)
                else:
                    db=max(db,-min(n.beat for n in selected))
                    for n in selected:
                        x=self.doc.note_x(n,self.window.cursor);n.beat=round(n.beat+db,8)
                        if abs(dx)>.01:n.line=self.doc.nearest_line(x+dx,self.window.cursor,n.beat)
                self.window.changed()
        self.viewport().update()
    def mouseDoubleClickEvent(self,event):
        n=self.hit(event.position())
        if n:self.window.selection={n.id};self.window.note_properties()
    def wheelEvent(self,event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.ppb=max(32,min(256,self.ppb*(1.2 if event.angleDelta().y()>0 else 1/1.2)))
            self.window.scroll_speed.setValue(self.ppb/64);self.sync()
        else:
            if self.window.playing():self.window.toggle_play()
            steps=self.wheel.steps(event,self.doc.step)
            if steps:self.window.seek(self.window.cursor+steps*self.doc.step)
        event.accept()

class Stage(QWidget):
    rectanglesChanged=Signal();selectedChanged=Signal()
    def __init__(self,window):
        super().__init__();self.window=window;self.setMinimumSize(280,190);self.editing=False;self.drawing=False;self.rects=copy.deepcopy([[0,0,1,1]]);self.selected=-1;self.drag=None;self.aspect=16/9;self.motions=[];self.events=[];self.motion_preview=False
    def frame(self):
        w=min(self.width()-24,(self.height()-28)*self.aspect);h=w/self.aspect
        return QRectF((self.width()-w)/2,8,w,h)
    def field(self):
        r=self.frame();margin=r.height()*48/600
        return QRectF(r.left()+margin,r.top(),r.width()-margin*2,r.height())
    def point(self,pos):
        r=self.field();return (max(0,min(1,(pos.x()-r.left())/r.width())),max(0,min(1,(pos.y()-r.top())/r.height())))
    def mapped(self,rect):
        r=self.field();l,t,right,b=rect;return QRectF(r.left()+l*r.width(),r.top()+t*r.height(),(right-l)*r.width(),(b-t)*r.height())
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.fillRect(self.rect(),BG)
        r=self.frame();f=self.field();p.fillRect(r,QColor('#0a1113'));doc=self.window.doc
        region=doc.region_at(self.window.cursor);rects=self.rects if self.editing else (region.rects if region else [])
        animated=not self.editing or self.motion_preview or self.window.playing()
        motions=self.motions if self.editing else (region.motions if region else [])
        events=self.events if self.editing else (region.events if region else [])
        p.save();p.setClipRect(r)
        union=QPainterPath()
        for i,rect in enumerate(rects):
            shape=QPainterPath()
            if animated:
                points=polygon(rect,motions[i] if motions else [],self.window.cursor,f.width()/f.height(),events[i] if events else {})
                shape.addPolygon(QPolygonF([QPointF(f.left()+x*f.width(),f.top()+y*f.height()) for x,y in points]));shape.closeSubpath()
            else:shape.addRect(self.mapped(rect))
            union=union.united(shape)
        p.setPen(QPen(MINT,2));p.setBrush(QColor(166,244,207,30));p.drawPath(union)
        if not animated:
            # Selection handles remain available without drawing interior rectangle borders.
            for i,rect in enumerate(rects):
                rr=self.mapped(rect);p.setPen(ORANGE if i==self.selected else INK);p.drawText(rr.adjusted(5,3,-4,-4),Qt.AlignmentFlag.AlignTop,f'{i+1}')
                if i==self.selected:p.fillRect(QRectF(rr.right()-7,rr.bottom()-7,7,7),ORANGE)
        p.restore()
        line=r.top()+r.height()*.8;p.setPen(QPen(INK,1));p.drawLine(QPointF(f.left(),line),QPointF(f.right(),line))
        if not self.editing:
            owner=getattr(self.window,'editor',None) or getattr(getattr(self.window,'panel',None),'editor',None) or self.window
            factor=getattr(owner,'scroll_factor',1.0)
            now=doc.seconds(self.window.cursor);speed=r.height()*.625/2.2*factor;unit=doc.bpm/60
            p.save();p.setClipRect(r)
            def position(beat,x,track):return QPointF(f.left()+x*f.width(),line-doc.seconds(track.distance(self.window.cursor,beat))*speed)
            horizons={track.id:track.horizon(self.window.cursor,2.9/factor*unit,doc.end_beat) for track in doc.lines}
            for track in doc.lines:
                points=track.samples(self.window.cursor,self.window.cursor,horizons[track.id],.035*unit/factor)
                color=QColor(MINT);color.setAlpha(round(track.pose(self.window.cursor)[1]*140));p.setPen(QPen(color,1.5))
                p.drawPolyline(QPolygonF([position(b,x,track) for b,x in points]));p.setBrush(color);p.drawEllipse(position(self.window.cursor,track.pose(self.window.cursor)[0],track),3,3)
            for n in doc.notes:
                t=doc.seconds(n.beat);end=doc.seconds(n.beat+n.length)
                track=doc.track(n.line)
                if track.distance(self.window.cursor,n.beat)>2.8/factor*unit or end<now-.15:continue
                start=max(n.beat,self.window.cursor) if n.length else n.beat
                width=f.width()*.092;head=position(start,doc.note_x(n,self.window.cursor,start),track)
                if n.length:
                    points=track.samples(self.window.cursor,start,min(n.beat+n.length,horizons[track.id]),.035*unit/factor)
                    shape=QPolygonF([position(b,x,track)+QPointF(-width/2,0) for b,x in points]+[position(b,x,track)+QPointF(width/2,0) for b,x in reversed(points)])
                    p.setPen(QPen(ORANGE,1));p.setBrush(QColor('#6e5940'));p.drawPolygon(shape)
                    tail=position(n.beat+n.length,doc.note_x(n,self.window.cursor,n.beat+n.length),track);p.fillRect(QRectF(tail.x()-width/2,tail.y()-2,width,4),ORANGE)
                p.fillRect(QRectF(head.x()-width/2,head.y()-2,width,4),ORANGE if n.length else MINT)
            p.restore()
        p.setPen(MUTED);p.setFont(QFont('Microsoft YaHei UI',8));p.drawText(QRectF(10,self.height()-20,self.width()-20,20),Qt.AlignmentFlag.AlignCenter,('区域动画草稿预览 · 关闭预览可编辑原始矩形' if animated else '原始矩形 · 拖画 / 移动 / 右下角缩放') if self.editing else ('Agent 草稿预览 · 尚未应用到主工程' if getattr(self.window,'agent_preview',False) else '游戏预览 · 固定判定线 · 与导出共用区域坐标'))
        p.end()
    def mousePressEvent(self,event):
        if not self.editing or self.motion_preview or self.window.playing() or event.button()!=Qt.MouseButton.LeftButton or not self.frame().contains(event.position()):return
        pos=self.point(event.position());hit=-1
        if not self.drawing:
            hit=next((i for i in range(len(self.rects)-1,-1,-1) if self.mapped(self.rects[i]).adjusted(-5,-5,5,5).contains(event.position())),-1)
        self.selected=hit
        if hit>=0:
            r=self.mapped(self.rects[hit]);resize=abs(event.position().x()-r.right())<12 and abs(event.position().y()-r.bottom())<12
            self.drag=('resize' if resize else 'move',pos,copy.deepcopy(self.rects[hit]))
        elif len(self.rects)<32:
            if not self.motions:self.motions=[[] for _ in self.rects]
            self.motions.append([])
            if self.events:self.events.append({})
            self.rects.append([pos[0],pos[1],pos[0]+.001,pos[1]+.001]);self.selected=len(self.rects)-1;self.drag=('new',pos,None)
        self.selectedChanged.emit();self.update()
    def mouseMoveEvent(self,event):
        if not self.drag:return
        kind,origin,old=self.drag;x,y=self.point(event.position());i=self.selected
        if kind=='new':self.rects[i]=[min(origin[0],x),min(origin[1],y),max(origin[0],x),max(origin[1],y)]
        elif kind=='resize':self.rects[i]=[old[0],old[1],max(old[0]+.01,x),max(old[1]+.01,y)]
        else:
            dx=max(-old[0],min(x-origin[0],1-old[2]));dy=max(-old[1],min(y-origin[1],1-old[3]));self.rects[i]=[old[0]+dx,old[1]+dy,old[2]+dx,old[3]+dy]
        self.rects[i]=[round(max(0,min(1,v)),4) for v in self.rects[i]];self.update();self.selectedChanged.emit()
    def mouseReleaseEvent(self,event):
        if not self.drag:return
        self.drag=None
        if self.selected>=0:
            l,t,r,b=self.rects[self.selected]
            if r-l<.01 or b-t<.01:
                self.rects.pop(self.selected);self.motions.pop(self.selected)
                if self.events:self.events.pop(self.selected)
                self.selected=-1
        self.update();self.selectedChanged.emit();self.rectanglesChanged.emit()
