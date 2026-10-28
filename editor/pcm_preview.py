"""Sample-indexed music + hit mixing. No per-hit playback devices or UI timers."""
from pathlib import Path
import wave
import numpy as np

RATE=48000
CHANNELS=2

def waveform_peaks(music):
    size=RATE//50;count=len(music)//size
    result=np.abs(music[:count*size].reshape(count,size,CHANNELS).astype(np.int32)).max(axis=(1,2)).astype(np.float32)/32768 if count else np.empty(0,dtype=np.float32)
    peaks=result.tolist()
    if len(music)%size:peaks.append(float(np.abs(music[count*size:].astype(np.int32)).max())/32768)
    return peaks

def read_hit(path):
    with wave.open(str(path),'rb') as source:
        if source.getframerate()!=RATE or source.getsampwidth()!=2 or source.getnchannels()!=1:
            raise ValueError('打击音素材必须是 48kHz / 16-bit / 单声道 PCM')
        return np.frombuffer(source.readframes(source.getnframes()),dtype='<i2').astype(np.float32)/32768

def mix_pcm(music,heads,sounds,gain,music_gain=.65):
    """All heads, including chords and overlaps, are summed at exact source frames."""
    mixed=music.astype(np.float32)/32768*music_gain
    placements=[]
    for seconds,kind,event_gain in heads:
        start=round(seconds*RATE);sample=sounds[kind];skip=max(0,-start);start=max(0,start)
        count=min(len(sample)-skip,len(mixed)-start)
        if count>0:
            mixed[start:start+count]+=sample[skip:skip+count,None]*gain*event_gain
            placements.append((start,count,kind))
    # A soft knee preserves transient timing while limiting summed chord peaks.
    mask=np.abs(mixed)>.9
    values=mixed[mask]
    mixed[mask]=np.sign(values)*(.9+.1*np.tanh((np.abs(values)-.9)/.1))
    return np.rint(np.clip(mixed,-1,1)*32767).astype('<i2'),placements

def render_mix(path,music,heads,sounds,gain):
    samples,_=mix_pcm(music,heads,sounds,gain)
    path=Path(path);temporary=path.with_suffix('.tmp')
    with wave.open(str(temporary),'wb') as target:
        target.setnchannels(CHANNELS);target.setsampwidth(2);target.setframerate(RATE);target.writeframes(samples.tobytes())
    temporary.replace(path)
    return str(path)
