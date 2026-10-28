"""Grid-aligned edge scrolling during Ctrl marquee gestures."""
from PySide6.QtCore import QObject,QTimer,QRectF,QPointF,QEvent,Qt

class EdgePan(QObject):
    def __init__(self,canvas):
        super().__init__(canvas);self.canvas=canvas;self.pos=None;self.anchor=None
        self.timer=QTimer(self);self.timer.setInterval(90);self.timer.timeout.connect(self.tick)
        canvas.installEventFilter(self);canvas.viewport().installEventFilter(self)
    def begin(self,pos):
        self.pos=QPointF(pos);self.anchor=(pos.x(),self.canvas.y_beat(pos.y()));self.timer.start()
    def move(self,pos):self.pos=QPointF(pos);self.update_box()
    def update_box(self):
        if self.anchor is None:return
        c=self.canvas;c.marquee=QRectF(QPointF(self.anchor[0],c.beat_y(self.anchor[1])),self.pos);c.viewport().update()
    def stop(self):self.timer.stop();self.anchor=None;self.pos=None
    def tick(self):
        if self.pos is None or not self.canvas.isVisible():self.stop();return
        c=self.canvas;y=self.pos.y();h=c.viewport().height();direction=1 if y<65 else -1 if y>h-36 else 0
        if not direction:return
        owner=getattr(c.window,'editor',c.window);owner.seek(c.window.cursor+direction*c.doc.step);self.update_box()
    def eventFilter(self,obj,event):
        if event.type() in (QEvent.Type.Hide,QEvent.Type.WindowDeactivate) or (event.type()==QEvent.Type.KeyRelease and event.key()==Qt.Key.Key_Control):self.timer.stop()
        return False
