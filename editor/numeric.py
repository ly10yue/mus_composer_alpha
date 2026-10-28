"""Numeric inputs keep unfinished text while playback refreshes the view."""
from PySide6.QtCore import Qt,QEvent
from PySide6.QtWidgets import QDoubleSpinBox,QApplication

class NumberBox(QDoubleSpinBox):
    def __init__(self,parent=None):
        super().__init__(parent);self.setKeyboardTracking(False)
    def event(self,event):
        if event.type()==QEvent.Type.ShortcutOverride:
            key=event.key();mods=event.modifiers()
            if key in (Qt.Key.Key_Left,Qt.Key.Key_Right,Qt.Key.Key_Home,Qt.Key.Key_End,Qt.Key.Key_Backspace,Qt.Key.Key_Delete) or (mods & Qt.KeyboardModifier.ControlModifier and key in (Qt.Key.Key_A,Qt.Key.Key_C,Qt.Key.Key_V,Qt.Key.Key_X,Qt.Key.Key_Z,Qt.Key.Key_Y)):
                event.accept();return True
        return super().event(event)

def sync_number(widget,value):
    focus=QApplication.focusWidget()
    if widget.hasFocus() or (focus is not None and widget.isAncestorOf(focus)):return
    previous=widget.blockSignals(True);widget.setValue(value);widget.blockSignals(previous)
