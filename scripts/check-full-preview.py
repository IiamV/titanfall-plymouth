#!/usr/bin/env python3
"""Verify actual closing frames, opening replacement, and native playback."""
import argparse
import json
from pathlib import Path
import subprocess
from full_sequence import interpolate

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--variant',default='full-custom')
args=parser.parse_args()
m=json.loads((ROOT/'build/manifest-full.json').read_text())
assert m['sequence']=='full'
intro=m['intros'][args.variant]
assert intro['source_sha256']==json.loads((ROOT/'theme/full/tracking.json').read_text())['source_sha256']
theme=ROOT/'build/themes'/f'titanfall-{args.variant}'
prefix=ROOT/'build'/f'plymouth-{args.variant}'
tracking=json.loads((ROOT/'theme/full/tracking.json').read_text())
occlusion=json.loads((ROOT/'theme/full/occlusion.json').read_text())
assert len(list(theme.glob('intro-*.png')))-len(list(theme.glob('intro-mask-*.png')))==intro['frames']
assert 0<=intro['duration']-tracking['duration']/m['speed']<1/m['fps']


def pixels(path,format='rgb24'):
    return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-pix_fmt',format,'-f','rawvideo','pipe:1'])


opening=pixels(theme/'opening.png')
for index in (0,int(m['fps']/m['speed']),int(2.4*m['fps']/m['speed'])):
    source_time=index/m['fps']*m['speed']
    source_index=min(range(len(tracking['frames'])),key=lambda i:abs(tracking['frames'][i]['time']-source_time))
    raw=pixels(ROOT/'build/full-source-frames'/f'{source_index}.png')
    actual=pixels(theme/f'intro-{index}.png')
    mask=pixels(theme/f'intro-mask-{index}.png','gray')
    gain=interpolate(occlusion['fade'],tracking['frames'][source_index]['time'])
    unchanged=replaced=0
    for point in range(0,960*540,97):
        i=point*3
        if mask[point]==0:
            assert actual[i:i+3]==raw[i:i+3], 'Cockpit footage changed outside the opening'
            unchanged+=1
        if mask[point]==255:
            assert max(abs(actual[i+c]-round(opening[i+c]*gain)) for c in range(3))<=1, 'Opening did not use the configured view'
            replaced+=1
    assert unchanged>500 and replaced>50, 'The opening mask does not preserve the cockpit and replace its view'

for label,seconds in (('intro-start',0),('intro-mid',1/m['speed']),('intro-closing',2.4/m['speed'])):
    actual=pixels(str(prefix)+f'-{label}.png')
    center=int(seconds*m['fps'])
    candidates=range(max(0,center-3),min(intro['frames'],center+4))
    assert any(actual==pixels(theme/f'intro-{index}.png') for index in candidates), f'{label}: native playback differs from actual precomposited video frames'
black=pixels(str(prefix)+'-intro-black.png')
assert max(black)<20,'Configured view remains visible after the cockpit closes to black'
assert pixels(str(prefix)+'-screenshot.png')==pixels(theme/'assembled.png'),'Full version did not finish at the configured light-up picture'
print(f'{args.variant}: real footage preserved, configured opening tracked, shutters occlude it, native playback and final light-up verified')
