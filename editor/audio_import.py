"""Persistent canonical Ogg imports; never alter a user's source recording."""
from pathlib import Path
import hashlib,uuid
from concurrent.futures import CancelledError
import numpy as np
import soundfile as sf
from pcm_preview import RATE,CHANNELS

def is_ogg(path):
    path=Path(path)
    try:
        with path.open('rb') as source:return path.suffix.lower()=='.ogg' and source.read(4)==b'OggS'
    except OSError:return False

def check_cancel(cancel):
    if cancel.is_set():raise CancelledError()

def conversion_path(source,folder,cancel):
    digest=hashlib.sha256(b'interval-ogg-48k-stereo-q8-v1')
    with Path(source).open('rb') as file:
        while chunk:=file.read(1024*1024):check_cancel(cancel);digest.update(chunk)
    return Path(folder)/(digest.hexdigest()+'.ogg')

def valid_conversion(path):
    try:
        info=sf.info(path)
        return info.format=='OGG' and info.subtype=='VORBIS' and info.samplerate==RATE and info.channels==CHANNELS and info.frames>0
    except (OSError,RuntimeError):return False

def write_ogg(raw,path,cancel):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.stem+'-'+uuid.uuid4().hex+'.tmp')
    music=np.frombuffer(raw,dtype='<i2').reshape(-1,CHANNELS)
    if not len(music):raise ValueError('歌曲没有可解码的音频')
    try:
        with sf.SoundFile(temporary,'w',samplerate=RATE,channels=CHANNELS,format='OGG',subtype='VORBIS',compression_level=.2) as output:
            for at in range(0,len(music),RATE):check_cancel(cancel);output.write(music[at:at+RATE])
        check_cancel(cancel)
        if not valid_conversion(temporary):raise ValueError('Ogg 转换结果校验失败')
        temporary.replace(path)
    finally:temporary.unlink(missing_ok=True)
    return path
