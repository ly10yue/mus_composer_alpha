"""Shared-clock PCM preview. Timer notifications never start sound playback."""
from bisect import bisect_left,bisect_right
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import sys,json,hashlib
from threading import Event
from concurrent.futures import CancelledError
import numpy as np
import soundfile as sf
from PySide6.QtCore import QObject,QTimer,Qt,QUrl,Signal,QThread,Slot
from PySide6.QtMultimedia import QAudioDecoder,QAudioFormat,QMediaPlayer
from pcm_preview import RATE,CHANNELS,read_hit,render_mix,waveform_peaks
from audio_import import is_ogg,conversion_path,valid_conversion,write_ogg

class HitTimeline:
    def reset(self,notes,beat):
        self.notes=sorted(notes,key=lambda n:(n.beat,n.id));self.beats=[n.beat for n in self.notes]
        self.index=bisect_left(self.beats,beat-1e-7)
    def due(self,beat,maximum_lag):
        end=bisect_right(self.beats,beat+1e-7);start=max(self.index,bisect_left(self.beats,beat-maximum_lag))
        result=self.notes[start:end];self.index=max(self.index,end);return result


class HitBank(QObject):
    """Settings and UI telemetry; audible hits are already inside the shared PCM."""
    triggered=Signal(int,bool)
    changed=Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self.enabled=True;self.volume=1.5;self.played_count=0
        root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'app/src/main/assets/sfx'
        self.samples={name:read_hit(root/(name+'.wav')) for name in ('tap','hold')}
        frame=np.arange(round(.03*RATE));envelope=(1-frame/len(frame))**3
        for name,hz in [('bar',1400),('beat',900)]:self.samples[name]=(8000/32768*np.sin(2*np.pi*hz*frame/RATE)*envelope).astype(np.float32)
    def ready(self):return all(len(sample) for sample in self.samples.values())
    def configure(self,enabled,volume):
        value=(bool(enabled),max(0.,min(2.,float(volume))))
        if value!=(self.enabled,self.volume):
            self.enabled,self.volume=value;self.changed.emit()
    def notify(self,hold,note_id):
        if self.enabled and self.volume>0:self.played_count+=1;self.triggered.emit(note_id,bool(hold))
    def stop(self):pass


class DecodeWorker(QObject):
    completed=Signal(int,object)
    failed=Signal(int,str)
    prepared=Signal(int,str,float)
    def __init__(self,conversion_folder):
        super().__init__();self.chunks=[];self.token=0;self.decoder=QAudioDecoder(self)
        self.conversion_folder=conversion_folder;self.cancel=Event();self.shutdown=Event();self.canonical=None;self.convert_target=None;self.decoding=False
        fmt=QAudioFormat();fmt.setSampleRate(RATE);fmt.setChannelCount(CHANNELS);fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16);self.decoder.setAudioFormat(fmt)
        self.decoder.bufferReady.connect(self.consume);self.decoder.finished.connect(self.finish);self.decoder.error.connect(self.error)
    @Slot(str,int)
    def decode(self,path,token):
        if self.shutdown.is_set():return
        self.decoding=False;self.decoder.stop();self.decoder.setSource(QUrl());self.chunks=[];self.token=token
        self.cancel.clear();self.canonical=Path(path);self.convert_target=None
        try:
            if not is_ogg(path):
                target=conversion_path(path,self.conversion_folder,self.cancel)
                if self.shutdown.is_set():return
                if valid_conversion(target):self.canonical=target
                else:
                    self.convert_target=target;self.decoder.setSource(QUrl.fromLocalFile(path));self.decoding=True;self.decoder.start();return
            self.read_canonical()
        except CancelledError:pass
        except Exception as error:self.failed.emit(token,str(error))
    def read_canonical(self):
        try:
            samples,rate=sf.read(self.canonical,dtype='int16',always_2d=True)
            if rate==RATE and samples.shape[1]==CHANNELS:
                self.complete(samples.astype('<i2',copy=False).tobytes());return
        except (OSError,RuntimeError):pass
        self.decoder.setSource(QUrl.fromLocalFile(str(self.canonical)));self.decoding=True;self.decoder.start()
    @Slot()
    def stop(self):self.decoding=False;self.decoder.stop();self.decoder.setSource(QUrl());self.chunks=[]
    @Slot()
    def consume(self):
        if not self.decoding:return
        buffer=self.decoder.read();fmt=buffer.format()
        if fmt.sampleFormat()!=QAudioFormat.SampleFormat.Int16 or fmt.channelCount()!=CHANNELS or fmt.sampleRate()!=RATE:
            self.decoder.stop();self.failed.emit(self.token,'PCM 格式不兼容');return
        self.chunks.append(bytes(buffer.constData()))
    @Slot()
    def finish(self):
        if not self.decoding:return
        self.decoding=False
        raw=b''.join(self.chunks);self.chunks=[]
        self.decoder.stop();self.decoder.setSource(QUrl())
        if self.shutdown.is_set() or self.cancel.is_set():return
        try:
            if self.convert_target is not None:
                self.canonical=write_ogg(raw,self.convert_target,self.cancel);self.convert_target=None;self.read_canonical()
            elif raw:self.complete(raw)
            else:raise ValueError('歌曲没有可解码的音频')
        except CancelledError:pass
        except Exception as error:self.failed.emit(self.token,str(error))
    def complete(self,raw):
        if self.shutdown.is_set() or self.cancel.is_set():return
        music=np.frombuffer(raw,dtype='<i2').reshape(-1,CHANNELS)
        info=sf.info(self.canonical)
        self.prepared.emit(self.token,str(self.canonical),info.frames/info.samplerate)
        self.completed.emit(self.token,(raw,waveform_peaks(music)))
    @Slot()
    def error(self,*args):
        if self.decoding and self.decoder.errorString():self.decoding=False;self.failed.emit(self.token,self.decoder.errorString())


class ComposerHits(QObject):
    rendered=Signal(object)
    decode_requested=Signal(str,int)
    decode_stopped=Signal()
    def __init__(self,editor):
        super().__init__(editor);self.editor=editor;self.bank=HitBank(self);self.bank.changed.connect(self.request_mix)
        self.timeline=None;self.document=None
        self.music=None;self.audio_key=None;self.generation=0;self.audio_generation=0;self.closed=False
        self.preparing=False;self.audio_error=''
        self.wanted_play=False;self.internal_pause=False;self.swapping=False;self.using_mix=False;self.mix_ready=False;self.mix_path=None;self.current_signature=None;self.swap_position=0
        self.cache=editor.cache/'pcm-preview';self.cache.mkdir(exist_ok=True)
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='preview-pcm')
        self.rendered.connect(self.finished)
        self.conversion_folder=editor.cache/'converted-audio';self.conversion_folder.mkdir(exist_ok=True)
        self.decode_thread=QThread(self);self.decode_worker=DecodeWorker(self.conversion_folder);self.decode_worker.moveToThread(self.decode_thread)
        self.decode_requested.connect(self.decode_worker.decode);self.decode_stopped.connect(self.decode_worker.stop)
        self.decode_worker.completed.connect(self.decoded);self.decode_worker.failed.connect(self.decode_error)
        self.decode_worker.prepared.connect(self.audio_prepared)
        self.decode_thread.finished.connect(self.decode_worker.deleteLater);self.decode_thread.start()
        self.mix_timer=QTimer(self);self.mix_timer.setSingleShot(True);self.mix_timer.timeout.connect(self.render)
        self.timer=QTimer(self);self.timer.setTimerType(Qt.TimerType.PreciseTimer);self.timer.setInterval(10);self.timer.timeout.connect(self.tick)
        editor.player.playbackStateChanged.connect(self.state_changed)
    def active_doc(self):
        stage=getattr(self.editor,'stage',None)
        return stage.window.doc if stage else self.editor.doc
    def load_document(self):
        self.generation+=1;self.audio_generation+=1;self.wanted_play=False;self.mix_timer.stop();self.decode_worker.cancel.set();self.decode_stopped.emit();self.music=None;self.timeline=None
        self.using_mix=False;self.mix_ready=False;self.current_signature=None;self.mix_path=None
        self.preparing=False;self.audio_error=''
        path=Path(self.editor.doc.audio)
        if not path.is_file():return
        stat=path.stat();self.audio_key=(str(path.resolve()),stat.st_size,stat.st_mtime_ns)
        self.preparing=not is_ogg(path)
        if self.preparing:self.editor.statusBar().showMessage('正在后台转换为 Ogg，转换完成后开始加载…')
        self.decode_requested.emit(str(path),self.audio_generation)
    def audio_prepared(self,token,path,duration):
        if self.closed or token!=self.audio_generation:return
        converted=self.preparing;self.preparing=False
        audio=Path(path);stat=audio.stat();self.audio_key=(str(audio.resolve()),stat.st_size,stat.st_mtime_ns)
        self.editor.audio_prepared(path,duration,converted)
    def decoded(self,token,result):
        if self.closed or token!=self.audio_generation:return
        raw,peaks=result
        self.music=np.frombuffer(raw,dtype='<i2').reshape(-1,CHANNELS)
        self.editor.waveform.peaks=peaks;self.editor.waveform.changed.emit()
        self.request_mix();self.mix_timer.start(0)
    def decode_error(self,token,message):
        if not self.closed and token==self.audio_generation:
            self.wanted_play=False;self.preparing=False;self.audio_error=message;self.editor.statusBar().showMessage('音频转换或解码失败：'+message,15000)
    def snapshot(self):
        doc=self.active_doc();heads=[(doc.seconds(n.beat)+doc.offset,'hold' if n.length else 'tap',1.) for n in sorted(doc.notes,key=lambda n:(n.beat,n.id))]
        gain=self.bank.volume if self.bank.enabled else 0.
        # Per-event gain keeps the metronome independent of the hit-volume slider.
        heads=[(seconds,kind,gain) for seconds,kind,_ in heads]
        if self.editor.metronome.isChecked():
            heads.extend((doc.seconds(beat)+doc.offset,'bar' if beat%doc.meter==0 else 'beat',.3) for beat in range(int(doc.end_beat)+1))
        signature=hashlib.sha256(json.dumps([self.audio_key,heads,'pcm-v2'],allow_nan=False).encode()).hexdigest()
        return signature,heads,gain
    def request_mix(self):
        if self.closed:return
        signature,_,_=self.snapshot()
        if signature==self.current_signature and self.mix_path and self.mix_path.is_file():return
        self.generation+=1;self.mix_ready=False
        if self.editor.playing():
            self.wanted_play=True;self.internal_pause=True;self.editor.player.pause();self.internal_pause=False
        self.mix_timer.start(120)
    def render(self):
        if self.music is None or self.closed:return
        token=self.generation;signature,heads,gain=self.snapshot();path=self.cache/('mix-'+signature+'.wav')
        if path.is_file():self.finished((token,path,signature,''));return
        self.editor.statusBar().showMessage('正在后台准备采样对齐的试听音轨…')
        future=self.executor.submit(render_mix,path,self.music,heads,self.bank.samples,1.)
        def completed(job):
            try:result=(token,Path(job.result()),signature,'')
            except Exception as error:result=(token,None,signature,str(error))
            try:self.rendered.emit(result)
            except RuntimeError:pass
        future.add_done_callback(completed)
    def finished(self,result):
        token,path,signature,error=result
        if self.closed or token!=self.generation:return
        if error:self.wanted_play=False;self.editor.statusBar().showMessage('试听音轨准备失败：'+error,15000);return
        self.swap_position=round(max(0,self.active_doc().seconds(self.editor.cursor)+self.active_doc().offset)*1000)
        self.mix_path=path;self.current_signature=signature;self.using_mix=True;self.mix_ready=False
        self.internal_pause=True;self.swapping=True
        if self.editor.playing():self.editor.player.pause()
        self.editor.audio_loaded=False;self.editor.player.setSource(QUrl.fromLocalFile(str(path)))
        self.swapping=False;self.internal_pause=False
        self.media_status(self.editor.player.mediaStatus())
        self.trim_cache()
    def media_status(self,status):
        if not self.using_mix:return False
        if self.swapping:return True
        if not self.mix_path or Path(self.editor.player.source().toLocalFile())!=self.mix_path:return True
        if status in (QMediaPlayer.MediaStatus.LoadedMedia,QMediaPlayer.MediaStatus.BufferedMedia):
            self.editor.audio_loaded=True
            if not self.mix_ready:
                self.mix_ready=True;self.editor.player.setPosition(self.swap_position)
                self.seek(max(0,(self.swap_position/1000-self.active_doc().offset)*self.active_doc().bpm/60))
                if self.wanted_play:self.editor.player.play()
                self.editor.statusBar().showMessage('同步 PCM 试听就绪 · 音乐与打击音共用同一音轨',5000)
        elif status==QMediaPlayer.MediaStatus.InvalidMedia:
            self.wanted_play=False;self.editor.audio_loaded=False;self.editor.statusBar().showMessage('同步试听音轨无法播放。',10000)
        return True
    def play(self):
        if self.audio_error:self.editor.statusBar().showMessage('请重新关联可播放的歌曲：'+self.audio_error,10000);return
        self.wanted_play=True
        if self.snapshot()[0]!=self.current_signature:self.request_mix()
        if self.mix_ready and not self.mix_timer.isActive():self.editor.player.play()
        else:
            self.editor.statusBar().showMessage('正在转换为 Ogg，完成后从当前位置播放…' if self.preparing else '正在准备同步试听，完成后从当前位置播放…')
            if self.music is not None:self.mix_timer.start(0)
    def pause(self):
        self.wanted_play=False;self.editor.player.pause()
    def invalidate(self):
        self.seek(self.editor.cursor);self.request_mix()
    def seek(self,beat):
        self.document=self.active_doc();self.timeline=HitTimeline();self.timeline.reset(self.document.notes,beat)
        self.swap_position=round(max(0,self.document.seconds(beat)+self.document.offset)*1000)
    def state_changed(self,state):
        if state==QMediaPlayer.PlaybackState.PlayingState:
            if self.timeline is None or self.document is not self.active_doc():self.seek(self.editor.cursor)
            self.timer.start()
        else:
            self.timer.stop()
            if state==QMediaPlayer.PlaybackState.PausedState and not self.internal_pause and self.mix_ready:self.wanted_play=False
            if state==QMediaPlayer.PlaybackState.StoppedState and self.mix_ready:self.wanted_play=False
    def tick(self):
        if not self.editor.playing() or self.timeline is None:return
        if self.document is not self.active_doc():
            self.seek(self.editor.cursor);self.request_mix();return
        seconds=self.editor.clock.seconds();doc=self.document
        for note in self.timeline.due((seconds-doc.offset)*doc.bpm/60,.15*doc.bpm/60):self.bank.notify(bool(note.length),note.id)
    def trim_cache(self):
        files=sorted(self.cache.glob('mix-*.wav'),key=lambda p:p.stat().st_mtime,reverse=True)
        for path in files[6:]:
            if path!=self.mix_path and path.resolve().parent==self.cache.resolve():
                try:path.unlink()
                except OSError:pass
    def close(self):
        if self.closed:return
        self.closed=True;self.generation+=1;self.timer.stop();self.mix_timer.stop();self.decode_worker.shutdown.set();self.decode_worker.cancel.set();self.decode_stopped.emit();self.decode_thread.quit();self.decode_thread.wait();self.executor.shutdown(wait=False,cancel_futures=True)
