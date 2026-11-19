#!/usr/bin/env python3
"""Check source identity, original-size shutter layers, and native playback."""
import argparse
import json
import math
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--variant',default='long-custom')
args=parser.parse_args()
profile=args.variant.rsplit('-',1)[0]
assert profile in ('long','semi-long'),'Use a long- or semi-long- variant'
m=json.loads((ROOT/f'build/manifest-{profile}.json').read_text())
intro=m['intros'][args.variant]
tracking=json.loads((ROOT/'theme/closing'/profile/'tracking.json').read_text())
theme=ROOT/'build/themes'/f'titanfall-{args.variant}'
prefix=ROOT/'build'/f'plymouth-{args.variant}'
layers=intro['layers']
assert intro['source_sha256']==tracking['source_sha256']==layers['source_sha256']
assert len(list(theme.glob('intro-*.png')))==intro['frames']
assert layers['source_last_frame']==(141 if profile=='long' else 27)
assert layers['crop']=={'top':[195,0,645,390],'bottom':[300,270,405,270]}
assert intro['fps']==layers['fps']==60
assert intro['trimmed_frames']==(1 if profile=='semi-long' else 0)
assert abs(intro['duration']-intro['movie_duration']-layers['duration'])<1e-8


def pixels(path,format='rgb24'):
    return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-pix_fmt',format,'-f','rawvideo','pipe:1'])


# Sample the actual premultiplied layer composition rather than comparing it
# with old opaque footage: the outside object intentionally remains removed.
points=list(range(0,960*540,193))
opening=pixels(theme/'opening.png')
static={name:pixels(theme/f'closing-{name}.png','rgba') for name in ('cockpit','wire')}


def expected(frame):
    pictures=[]
    for name in ('bottom','cockpit','wire','top'):
        if name in static:pictures.append((static[name],[0,0,960,540]))
        else:pictures.append((pixels(theme/f'closing-{name}-{frame}.png','rgba'),layers['crop'][name]))
    seconds=frame/layers['fps']
    fade=min(1,max(0,(seconds-layers['fade_start'])/(layers['fade_end']-layers['fade_start'])))
    result=[]
    for point in points:
        rgb=list(opening[point*3:point*3+3]);x,y=point%960,point//960
        for picture,(ox,oy,w,h) in pictures:
            if not (ox<=x<ox+w and oy<=y<oy+h):continue
            index=((y-oy)*w+x-ox)*4;a=picture[index+3]/255
            rgb=[round(rgb[c]*(1-a)+picture[index+c]*a) for c in range(3)]
        result.extend(round(v*(1-fade)) for v in rgb)
    return result


for label,seconds in intro['checkpoints'].items():
    actual=pixels(str(prefix)+f'-intro-{label}.png')
    if label=='black':
        assert max(actual)<20,'View/HUD flash remains after closing'
        continue
    sample=[actual[p*3+c] for p in points for c in range(3)]
    if seconds<intro['movie_duration']:
        center=round(seconds*intro['fps']);slack=max(4,math.ceil(intro['frames']*.1))
        errors=[]
        for frame in range(max(0,center-slack),min(intro['frames'],center+slack+1)):
            reference=pixels(theme/f'intro-{frame}.png')
            errors.append(sum(abs(sample[i*3+c]-reference[p*3+c]) for i,p in enumerate(points) for c in range(3))/len(sample))
    else:
        center=round((seconds-intro['movie_duration'])*layers['fps'])
        slack=max(5,math.ceil(intro['frames']*.1))
        errors=[sum(abs(a-b) for a,b in zip(sample,expected(frame)))/len(sample)
                for frame in range(max(0,center-slack),min(layers['frames'],center+slack+1))]
    error=min(errors)
    assert error<1.5,f'{label}: native recorded-layer playback differs (RGB error {error:.2f})'
    print(f'  {label}: native composition RGB error {error:.3f}')
assert pixels(str(prefix)+'-screenshot.png')==pixels(theme/'assembled.png'),'Final light-up picture differs'
print(f'{args.variant}: recorded shutters, original size, layer order, black hold, and final picture verified')
