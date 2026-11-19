#!/usr/bin/env python3
"""Verify actual closing frames, moving opening, and native playback."""
import argparse
import json
import math
from pathlib import Path
import subprocess
from full_sequence import DATA, interpolate

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--variant',default='long-custom')
args=parser.parse_args()
profile=args.variant.rsplit('-',1)[0]
assert profile in ('long','semi-long'),'Use a long- or semi-long- variant'
m=json.loads((ROOT/f'build/manifest-{profile}.json').read_text())
assert m['sequence']==profile
intro=m['intros'][args.variant]
tracking=json.loads((DATA/profile/'tracking.json').read_text())
assert intro['source_sha256']==tracking['source_sha256']
theme=ROOT/'build/themes'/f'titanfall-{args.variant}'
prefix=ROOT/'build'/f'plymouth-{args.variant}'
assert len(list(theme.glob('intro-*.png')))-len(list(theme.glob('intro-mask-*.png')))==intro['frames']
assert 0<=intro['duration']-tracking['duration']/m['speed']<1/m['fps']


def pixels(path,format='rgb24'):
    return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-pix_fmt',format,'-f','rawvideo','pipe:1'])


opening=pixels(theme/'opening.png')
for label in ('start','moving','closing'):
    index=round(intro['checkpoints'][label]*m['fps'])
    source_time=index/m['fps']*m['speed']
    source_index=min(range(len(tracking['frames'])),key=lambda i:abs(tracking['frames'][i]['time']-source_time))
    raw=pixels(ROOT/f'build/{profile}-source-frames'/f'{source_index}.png')
    actual=pixels(theme/f'intro-{index}.png')
    mask=pixels(theme/f'intro-mask-{index}.png','gray')
    expected_mask=pixels(DATA/'masks'/f'{tracking["frames"][source_index]["mask"]}.png','gray')
    assert mask==expected_mask,'Mask is not synchronized to the selected source frame'
    gain=interpolate(tracking['fade'],tracking['frames'][source_index]['time'])
    unchanged=replaced=0
    for point in range(0,960*540,97):
        i=point*3
        if mask[point]==0:
            assert actual[i:i+3]==raw[i:i+3],'Cockpit footage changed outside the opening'
            unchanged+=1
        if mask[point]==255:
            assert max(abs(actual[i+c]-round(opening[i+c]*gain)) for c in range(3))<=1,'Opening did not use the configured view'
            replaced+=1
    assert unchanged>100 and replaced>50,'Mask does not preserve the cockpit and replace its view'

for label,seconds in intro['checkpoints'].items():
    actual=pixels(str(prefix)+f'-intro-{label}.png')
    center=round(seconds*m['fps'])
    # Refresh callbacks can run late while Plymouth decodes footage PNGs.
    # Verify actual frame identity within 10% timing slack, not wall-clock
    # precision that the script plugin does not guarantee.
    slack=max(3,math.ceil(intro['frames']*0.1))
    candidates=range(max(0,center-slack),min(intro['frames'],center+slack+1))
    assert any(actual==pixels(theme/f'intro-{index}.png') for index in candidates),f'{label}: native playback differs from actual video frames'
black=pixels(str(prefix)+'-intro-black.png')
color=m['palettes'][args.variant]['panel']
blank=bytes(int(color[i:i+2],16) for i in (1,3,5))*(960*540)
assert max(black)<20 or black==blank,'Configured view remains visible after cockpit closes'
assert pixels(str(prefix)+'-screenshot.png')==pixels(theme/'assembled.png'),'Did not finish at configured light-up picture'
print(f'{args.variant}: source-frame/mask synchronization, real cockpit and shutters, native playback, final light-up verified')
