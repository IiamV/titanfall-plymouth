#!/usr/bin/env python3
"""Anchor headless light-up captures to the actual first line refresh.

Plymouth refresh callbacks can slip while decoding video frames. This observes
Xvfb only; it never changes the theme's timing or talks to a host daemon.
"""
import json
from pathlib import Path
import struct
import sys
import time


def framebuffer(path,color):
    raw=path.read_bytes()
    header=struct.unpack('>25I',raw[:100])
    size,_,_,_,width,height,_,order,_,_,_,bits,stride,_,red,green,blue,_,_,colors,*_=header
    if bits not in (24,32):raise ValueError('Expected a 24/32-bit Xvfb framebuffer')
    data=raw[size+colors*12:size+colors*12+height*stride]
    byteorder='little' if order==0 else 'big'
    value=int.from_bytes(data[:bits//8],byteorder)&~(red|green|blue)
    for channel,mask in zip(color,(red,green,blue)):
        shift=(mask&-mask).bit_length()-1
        value|=(channel<<shift)&mask
    pixel=value.to_bytes(bits//8,byteorder)
    row=pixel*width+bytes(stride-width*(bits//8))
    return data==row*height,raw


def main():
    path,manifest,target=map(Path,sys.argv[1:4])
    m=json.loads(manifest.read_text());palette=next(iter(m['palettes'].values()))
    color=tuple(int(palette['panel'][i:i+2],16) for i in (1,3,5))
    deadline=time.monotonic()+5
    blank=False
    while time.monotonic()<deadline:
        uniform,raw=framebuffer(path,color)
        if uniform and not blank:
            target.write_bytes(raw);blank=True
        if blank and not uniform:
            # First nonzero line frame lands one refresh after entrance starts.
            print(time.monotonic()-m['timeline_offset']-m['lines']['entrance_start']-1/m['fps'])
            return
        time.sleep(.004)
    raise SystemExit('Could not observe video-to-light-up handoff')


if __name__=='__main__':main()
