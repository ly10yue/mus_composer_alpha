"""One musical time axis shared by bound notes and three parameter lanes."""
import copy,math
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QPainter,QColor,QPen,QFont,QPolygonF
from PySide6.QtWidgets import QAbstractScrollArea
from curves import EASES,EASE_NAMES,eased
from timeline_edit import GridWheel
from edge_pan import EdgePan
from versioning import display_factor
from views import BG,PANEL,MINT,ORANGE,INK,MUTED,GRID

PROPS=('notes','x','alpha','speed')
TITLES=('绑定音符','横向位置','线透明度','音符流速')
COLORS=(MINT,QColor('#83c9f4'),QColor('#d6b4fa'),ORANGE)

class TrackTimeline(QAbstractScrollArea):
    def __init__(self,window):
        super().__init__();self.window=window;self.ppb=64.;self.ruler=76;self.drag=None;self.marquee=None;self.wheel=GridWheel();self.edge=EdgePan(self)
        self.setMinimumWidth(440);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus);self.viewport().setMouseTracking(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn);self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.verticalScrollBar().valueChanged.connect(self.scrub)
    @property
    def doc(self):return self.window.doc
    def judgement_y(self):return self.viewport().height()*.8
    def beat_y(self,beat):return self.judgement_y()-(beat-self.window.cursor)*self.ppb
    def y_beat(self,y):return self.window.cursor+(self.judgement_y()-y)/self.ppb
    def lane(self,column):
        width=(self.viewport().width()-self.ruler-8)/4
        return QRectF(self.ruler+column*width,30,width,self.viewport().height()-30)
    def column(self,x):return min(3,int((x-self.ruler)/self.lane(0).width())) if x>=self.ruler else -1
    def sync(self):
        bar=self.verticalScrollBar();bar.blockSignals(True);bar.setRange(0,round(self.doc.end_beat*1000));bar.setSingleStep(max(1,round(self.doc.step*1000)));bar.setPageStep(round(self.viewport().height()/self.ppb*1000));bar.setValue(round(self.window.cursor*1000));bar.blockSignals(False);self.viewport().update()
    def resizeEvent(self,event):super().resizeEvent(event);self.sync()
    def ensure_beat(self,beat):
        bar=self.verticalScrollBar();bar.blockSignals(True);bar.setValue(round(beat*1000));bar.blockSignals(False);self.viewport().update()
    def scrollContentsBy(self,dx,dy):self.viewport().update()
    def scrub(self,value):self.window.pause();self.window.editor.seek(value/1000)
    def items(self):
        for note in self.doc.notes:
            if 'notes' in self.window.PROPS and note.line==self.window.track.id:yield ('notes',note.id),note.beat,note.beat+note.length,note
        for prop in self.window.PROPS:
            if prop=='notes':continue
            for index,event in enumerate(self.window.track.segments(prop)):yield (prop,index),event['start'],event['end'],event
    def bounds(self,prop,start,end):
        cell=self.lane(self.window.PROPS.index(prop));top=self.beat_y(end);bottom=self.beat_y(start)
        return QRectF(cell.left()+9,top-5 if start==end else top,cell.width()-18,max(10,bottom-top))
    def hit(self,pos):
        return next((item for item in reversed(list(self.items())) if self.bounds(item[0][0],item[1],item[2]).adjusted(0,-4,0,4).contains(pos)),None)
    def paintEvent(self,event):
        p=QPainter(self.viewport());p.setRenderHint(QPainter.RenderHint.Antialiasing);p.fillRect(self.viewport().rect(),BG);p.setFont(QFont('Microsoft YaHei UI',9))
        height=self.viewport().height();width=self.viewport().width();first=max(0,self.y_beat(height)-1);last=min(self.doc.end_beat,self.y_beat(30)+1)
        p.save();p.setClipRect(QRectF(0,30,width,height-30))
        for column in range(4):
            cell=self.lane(column);p.fillRect(cell,QColor('#142022') if column%2 else BG);p.setPen(GRID);p.drawLine(cell.topLeft(),cell.bottomLeft())
        p.fillRect(QRectF(0,self.judgement_y(),width,height-self.judgement_y()),QColor(6,12,14,115))
        if self.ppb*self.doc.step>=5:
            p.setPen(QColor('#243536'))
            for i in range(int(first/self.doc.step),math.ceil(last/self.doc.step)+1):
                y=self.beat_y(i*self.doc.step);p.drawLine(QPointF(self.ruler,y),QPointF(width,y))
        for beat in range(int(first),math.ceil(last)+1):
            y=self.beat_y(beat);bar=beat%self.doc.meter==0;p.setPen(QPen(QColor('#5b7e70') if bar else GRID,1.6 if bar else 1));p.drawLine(QPointF(self.ruler,y),QPointF(width,y))
            p.setPen(MINT if bar else MUTED);p.drawText(QRectF(3,y-10,self.ruler-9,20),Qt.AlignmentFlag.AlignRight,f'{beat//self.doc.meter+1:03d}:{beat%self.doc.meter+1}')
        for selected,start,end,item in self.items():
            if end<first or start>last:continue
            prop,index=selected;column=self.window.PROPS.index(prop);color=COLORS[column];rect=self.bounds(prop,start,end)
            fill=QColor(color);fill.setAlpha(65 if selected in self.window.selection else 30);p.setBrush(fill);p.setPen(QPen(INK if selected in self.window.selection else color,2 if selected in self.window.selection else 1));p.drawRoundedRect(rect,4,4)
            if prop=='notes':
                p.fillRect(QRectF(rect.left(),self.beat_y(start)-4,rect.width(),8),ORANGE if item.length else MINT)
                if item.length:p.fillRect(QRectF(rect.left(),self.beat_y(end)-2,rect.width(),4),ORANGE)
                p.setPen(INK);p.drawText(rect.adjusted(4,4,-4,-4),Qt.AlignmentFlag.AlignCenter,'HOLD' if item.length else '')
            else:
                vector=isinstance(item['from'],list)
                pairs=list(zip(item['from'],item['to'])) if vector else [(item['from'],item['to'])]
                for component,(a,b) in enumerate(pairs):
                    low=min(0,a,b);maximum=max(1,a,b)-low
                    points=[QPointF(rect.left()+7+(rect.width()-14)*(a+(b-a)*eased(j/24,item.get('ease','linear'))-low)/maximum,self.beat_y(start+(end-start)*j/24)) for j in range(25)]
                    p.setPen(QPen(color if component==0 else ORANGE,1.4));p.drawPolyline(QPolygonF(points))
                def label(value):return ', '.join(f'{v*display_factor(prop):g}' for v in value) if isinstance(value,list) else f'{value*display_factor(prop):g}'
                p.setPen(INK)
                if rect.height()>45:
                    p.drawText(rect.adjusted(5,2,-5,-2),Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignRight,'终 '+label(item['to']))
                    p.drawText(rect.adjusted(5,2,-5,-2),Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignLeft,'始 '+label(item['from']))
                else:p.drawText(rect.adjusted(4,1,-4,-1),Qt.AlignmentFlag.AlignCenter,label(item['from'])+' → '+label(item['to']))
                if rect.height()>78:
                    name=EASE_NAMES[EASES.index(item.get('ease','linear'))].replace('Sin · ','Sin\n')
                    p.drawText(rect.adjusted(3,19,-3,-19),Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,name)
                if selected in self.window.selection:
                    for y in (rect.top(),rect.bottom()):p.fillRect(QRectF(rect.center().x()-13,y-2,26,4),INK)
        if self.drag and self.drag['mode']=='create':
            a,b=sorted((self.drag['anchor'],self.drag['last']));rect=self.bounds(self.drag['prop'],a,b);p.setPen(INK);p.setBrush(QColor(255,255,255,25));p.drawRect(rect)
        if self.marquee is not None:p.setPen(MINT);p.setBrush(QColor(166,244,207,35));p.drawRect(self.marquee.normalized())
        y=self.judgement_y();p.setPen(QPen(ORANGE,2));p.drawLine(QPointF(0,y),QPointF(width,y));p.fillRect(QRectF(0,y-23,self.ruler,46),PANEL);p.setPen(ORANGE);p.drawText(7,round(y-5),'判定线');p.drawText(7,round(y+15),f'{self.window.cursor:.2f}')
        p.restore();p.fillRect(QRectF(0,0,width,30),PANEL);p.setPen(MUTED);p.drawText(7,20,'小节 : 拍')
        for column,title in enumerate(self.window.LABELS):
            cell=self.lane(column);p.setPen(COLORS[column]);p.drawText(QRectF(cell.left(),0,cell.width(),30),Qt.AlignmentFlag.AlignCenter,title)
        p.end()
    def mousePressEvent(self,event):
        self.setFocus();pos=event.position()
        if pos.y()<30:return
        self.window.pause();item=self.hit(pos)
        if event.button()==Qt.MouseButton.RightButton:
            if item:self.window.select(item[0]);self.window.delete_selected()
            return
        if event.button()!=Qt.MouseButton.LeftButton:return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.marquee=QRectF(pos,pos);self.drag=dict(mode='box',origin=pos);self.edge.begin(pos);return
        raw=self.y_beat(pos.y());beat=self.doc.snap(raw);column=self.column(pos.x())
        if column<0:self.window.editor.seek(beat);return
        if raw<0 or beat>self.doc.end_beat:return
        prop=self.window.PROPS[column]
        if prop=='notes' and self.window.tool=='tap':self.window.add_note(beat);return
        if item and (prop!='notes' or self.window.tool=='select'):
            selected,start,end,data=item;self.window.select(selected);mode='move'
            if end>start:
                if abs(pos.y()-self.beat_y(end))<8:mode='end'
                elif abs(pos.y()-self.beat_y(start))<8:mode='start'
            self.drag=dict(mode=mode,anchor=beat,last=beat,prop=prop,selected=selected,start=start,end=end,data=copy.deepcopy(data));return
        if prop=='notes' and self.window.tool=='select':self.window.select(None);self.window.editor.seek(beat);return
        self.drag=dict(mode='create',anchor=beat,last=beat,prop=prop)
    def mouseMoveEvent(self,event):
        if self.drag and self.drag['mode']=='box':self.edge.move(event.position());return
        if self.drag:self.drag['last']=min(self.doc.end_beat,self.doc.snap(self.y_beat(event.position().y())));self.viewport().update()
        else:
            item=self.hit(event.position())
            if item:self.viewport().setToolTip(f'{item[1]:g} → {item[2]:g} 拍；双击编辑数值，右键删除')
            else:self.viewport().setToolTip('')
    def mouseReleaseEvent(self,event):
        if not self.drag:return
        drag=self.drag;self.drag=None;self.edge.stop()
        if drag['mode']=='box':
            rect=self.marquee.normalized();self.marquee=None;self.window.select_many(key for key,start,end,data in self.items() if rect.intersects(self.bounds(key[0],start,end)));return
        prop=drag['prop']
        if drag['mode']=='create':
            if prop=='notes':self.window.add_note(drag['anchor'],drag['last'])
            else:self.window.create_interval(prop,drag['anchor'],drag['last'])
        elif abs(drag['last']-drag['anchor'])>1e-8:
            delta=drag['last']-drag['anchor'];start,end=drag['start'],drag['end']
            if drag['mode']=='move':delta=max(-start,min(delta,self.doc.end_beat-end));start+=delta;end+=delta
            elif drag['mode']=='start':start=max(0,min(start+delta,end-self.doc.step))
            else:end=min(self.doc.end_beat,max(end+delta,start+self.doc.step))
            if prop=='notes':
                note=next(n for n in self.doc.notes if n.id==drag['selected'][1]);self.window.update_note(note,start,end)
            else:
                item=dict(drag['data'],start=start,end=end);self.window.store_event(prop,item,drag['selected'][1])
        self.viewport().update()
    def mouseDoubleClickEvent(self,event):
        item=self.hit(event.position())
        if item:
            self.drag=None;self.window.select(item[0]);box=self.window.start if item[0][0]=='notes' else self.window.value_from;box.setFocus();box.selectAll()
    def wheelEvent(self,event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:self.window.zoom.setValue(self.window.zoom.value()*(1.2 if event.angleDelta().y()>0 else 1/1.2))
        else:
            self.window.pause();steps=self.wheel.steps(event,self.doc.step)
            if steps:self.window.editor.seek(self.window.cursor+steps*self.doc.step)
        event.accept()
    def keyPressEvent(self,event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() in (Qt.Key.Key_C,Qt.Key.Key_V,Qt.Key.Key_A):
            if event.key()==Qt.Key.Key_C:self.window.copy_selected()
            elif event.key()==Qt.Key.Key_V:self.window.paste_selected()
            else:self.window.select_many(item[0] for item in self.items())
            event.accept();return
        if event.key()==Qt.Key.Key_Delete:self.window.delete_selected();event.accept()
        else:super().keyPressEvent(event)
