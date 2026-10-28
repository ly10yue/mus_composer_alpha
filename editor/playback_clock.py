"""Smooth visual time, corrected against the audio player's coarse timestamps."""
import time

class PlaybackClock:
    def __init__(self,now=time.perf_counter):
        self.now=now;self.rate=1.;self.reset(0)
    def reset(self,seconds,running=False,rate=None):
        if rate is not None:self.rate=rate
        self.anchor=self.raw=self.last=max(0.,seconds);self.wall=self.report_wall=self.now()
        self.running=running;self.advancing=False
    def seconds(self):
        value=self.anchor
        if self.running and self.advancing:
            value=min(self.anchor+(self.now()-self.wall)*self.rate,self.raw+.15*self.rate)
        self.last=max(self.last,value)
        return self.last
    def start(self,seconds,rate):self.reset(seconds,True,rate)
    def pause(self):
        value=self.seconds();self.reset(value,False)
    def set_rate(self,rate):
        value=self.seconds();self.anchor=value;self.wall=self.now();self.rate=rate
    def observe(self,seconds):
        if not self.running or abs(seconds-self.raw)<1e-8:return
        now=self.now()
        # Ignore an old queued position immediately after an explicit seek.
        if not self.advancing and abs(seconds-self.raw)>.3 and now-self.wall<.5:return
        if seconds<self.raw-.02:
            self.reset(seconds,True);return
        if not self.advancing:
            self.anchor=max(self.last,seconds);self.advancing=True
        else:
            predicted=self.seconds();error=seconds-predicted
            if abs(error)>.25:self.reset(seconds,True);self.advancing=True;return
            self.anchor=predicted+.15*error
        self.raw=seconds;self.wall=self.report_wall=now
    def beat(self,bpm,offset):return max(0.,(self.seconds()-offset)*bpm/60)
