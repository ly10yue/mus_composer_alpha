from array import array
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat

class Waveform(QObject):
    changed=Signal();failed=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent);self.peaks=[];self.decoder=QAudioDecoder(self)
        self.decoder.bufferReady.connect(self.consume);self.decoder.finished.connect(self.changed)
        self.decoder.error.connect(lambda *_:self.failed.emit(self.decoder.errorString()))
    def load(self,path):
        self.decoder.stop();self.peaks=[];self.decoder.setSource(QUrl.fromLocalFile(str(path)));self.decoder.start()
    def consume(self):
        b=self.decoder.read();fmt=b.format();kind=fmt.sampleFormat()
        if kind==QAudioFormat.SampleFormat.Float:code='f';scale=1
        elif kind==QAudioFormat.SampleFormat.Int16:code='h';scale=32768
        elif kind==QAudioFormat.SampleFormat.Int32:code='i';scale=2147483648
        else:return
        samples=array(code);samples.frombytes(bytes(b.constData()))
        peak=min(1,max((abs(x)/scale for x in samples[::max(1,fmt.channelCount()*4)]),default=0))
        start=max(0,int(b.startTime()/1e6*50));end=max(start+1,int((b.startTime()+b.duration())/1e6*50))
        if end>len(self.peaks):self.peaks.extend([0.]*(end-len(self.peaks)))
        for i in range(start,end):self.peaks[i]=max(self.peaks[i],peak)
        if start%25==0:self.changed.emit()
