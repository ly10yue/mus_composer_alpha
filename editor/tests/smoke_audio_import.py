"""Normalize real MP3/WAV/FLAC imports before preview, save and export."""
import os,sys,time,json,uuid,hashlib,zipfile
from pathlib import Path
import numpy as np,soundfile as sf
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'editor'))
from main import QApplication,Editor,QFileDialog
from model import Document,export_package,atomic_json
app=QApplication([]);app.setApplicationName('IntervalAudioImportTests-'+uuid.uuid4().hex[:8]);w=Editor(False);w.show();w.output.setVolume(0)
out=ROOT/'build/audio-import-tests';out.mkdir(parents=True,exist_ok=True);reports=[]
def fixture(path,rate,channels,**options):
    music=np.zeros(rate*6,dtype=np.float32)
    for at in np.arange(.5,6,.5):
        first=round(at*rate);v=np.arange(round(.06*rate));music[first:first+len(v)]=.6*np.sin(2*np.pi*1800*v/rate)*np.minimum(1,v/60)*np.minimum(1,(len(v)-v)/60)
    sf.write(path,music if channels==1 else np.column_stack((music,music)),rate,**options)
def until(fn,timeout=15):
    end=time.perf_counter()+timeout
    while not fn() and time.perf_counter()<end:app.processEvents();time.sleep(.001)
    assert fn(),(w.cursor,w.hit_audio.preparing,w.hit_audio.audio_error,w.statusBar().currentMessage())
try:
    fixtures=[]
    for name,rate,channels,options in [
        ('clicks-cbr.mp3',44100,1,dict(format='MP3',subtype='MPEG_LAYER_III',bitrate_mode='CONSTANT',compression_level=.25)),
        ('clicks-vbr.mp3',48000,2,dict(format='MP3',subtype='MPEG_LAYER_III',bitrate_mode='VARIABLE',compression_level=.2)),
        ('clicks-mono-44100.wav',44100,1,dict(subtype='PCM_16')),
        ('clicks-stereo-48000.wav',48000,2,dict(subtype='FLOAT')),
        ('clicks-22050.flac',22050,1,dict(format='FLAC'))]:
        path=out/name;fixture(path,rate,channels,**options);fixtures.append(path)
    for source in fixtures:
        before=hashlib.sha256(source.read_bytes()).hexdigest();doc=Document(bpm=120,duration=6,audio=str(source.resolve()));doc.add(1,'line1');w.replace_document(doc,None)
        assert w.player.source().isEmpty();assert w.hit_audio.preparing;assert not w.export_ready();w.toggle_play()
        until(lambda:w.hit_audio.mix_ready and w.cursor>.6);w.hit_audio.pause()
        canonical=Path(w.doc.audio);info=sf.info(canonical)
        assert canonical.suffix=='.ogg' and info.format=='OGG' and info.subtype=='VORBIS' and info.samplerate==48000 and info.channels==2
        assert abs(info.duration-6)<.015 and not w.hit_audio.audio_error
        music=w.hit_audio.music[:,0].astype(np.float32)/32768;energy=np.sqrt(np.mean(music[:len(music)//480*480].reshape(-1,480)**2,axis=1))
        starts=(np.flatnonzero((energy[1:]>.1)&(energy[:-1]<=.1))+1)/100
        assert len(starts)==11 and np.max(np.abs(starts-np.arange(.5,6,.5)))<=.02,starts
        w.seek(0);frames=[]
        def frame():
            if w.playing():frames.append((time.perf_counter(),w.cursor))
        w.frameRendered.connect(frame);w.toggle_play();until(lambda:w.cursor>5.1);w.hit_audio.pause();w.frameRendered.disconnect(frame)
        def cross(beat):
            for (a,x),(b,y) in zip(frames,frames[1:]):
                if x<=beat<=y and y>x:return a+(b-a)*(beat-x)/(y-x)
            raise AssertionError(beat)
        duration=cross(5)-cross(1);assert abs(duration-2)<.05,(source.name,duration)
        stat=canonical.stat().st_mtime_ns;project=out/'converted.ivproj';w.path=project;assert w.save()
        export_package(w.doc,out/'converted.interval')
        with zipfile.ZipFile(out/'converted.interval') as package:
            chart=json.loads(package.read('chart.json'));assert chart['audio']=='music.ogg' and package.read('music.ogg').startswith(b'OggS')
        assert before==hashlib.sha256(source.read_bytes()).hexdigest()
        w.open_path(project);until(lambda:w.hit_audio.mix_ready);assert Path(w.doc.audio)==canonical and canonical.stat().st_mtime_ns==stat
        reports.append(dict(source=source.name,duration=info.duration,measuredBarSeconds=duration,firstBeatSeconds=float(starts[0]),format=info.format,samplerate=info.samplerate,channels=info.channels))
        print('PASS',reports[-1],flush=True)
    # JSON export includes the normalized Ogg next to the JSON.
    get_name=QFileDialog.getSaveFileName
    try:
        QFileDialog.getSaveFileName=lambda *a,**k:(str(out/'converted.json'),'JSON')
        w.export_json();chart=json.loads((out/'converted.json').read_text(encoding='utf-8'));assert (out/chart['audio']).read_bytes().startswith(b'OggS')
    finally:QFileDialog.getSaveFileName=get_name
    original=ROOT/'app/src/main/assets/desultory-signals.ogg';w.replace_document(Document(audio=str(original)),None);until(lambda:w.hit_audio.mix_ready);assert Path(w.doc.audio)==original
    # An old project that still refers to MP3 is normalized on opening.
    old=Document(bpm=120,duration=6,audio=str(fixtures[0].resolve()));atomic_json(out/'old-mp3.ivproj',old.project());w.open_path(out/'old-mp3.ivproj');until(lambda:w.hit_audio.mix_ready);assert Path(w.doc.audio).suffix=='.ogg'
    w.replace_document(Document(audio=str(fixtures[1].resolve())),None);w.replace_document(Document(audio=str(original)),None);until(lambda:w.hit_audio.mix_ready);assert Path(w.doc.audio)==original
    broken=out/'broken.mp3';broken.write_bytes(b'invalid audio');w.replace_document(Document(audio=str(broken)),None);until(lambda:bool(w.hit_audio.audio_error));assert not w.hit_audio.mix_ready and not w.export_ready()
    atomic_json(out/'report.json',reports)
    print('PASS: uncached conversion, CBR/VBR MP3, mono/stereo WAV, FLAC, beat onsets/bar timing, source preservation, pending play, export, reopen/cache, old projects, switch/cancel and invalid audio')
finally:w.dirty=False;w.region_dirty=False;w.close()
