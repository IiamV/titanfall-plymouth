#!/usr/bin/env python3
"""Development-only matte bake; normal theme builds need no OpenCV/NumPy.

Uses reviewed per-keyframe masks, not a single projected outline.
Optical-flow reference: https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html
"""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'theme/closing'


def main():
    try:
        import cv2
        import numpy as np
    except ImportError:
        raise SystemExit('Calibration needs OpenCV and NumPy in a development environment. Ordinary builds use the baked mattes.')
    tracking=json.loads((DATA/'long/tracking.json').read_text())
    source=ROOT/tracking['source']
    if hashlib.sha256(source.read_bytes()).hexdigest()!=tracking['source_sha256']:
        raise SystemExit('Source changed; review and recalibrate keymasks before baking.')
    width,height=json.loads((DATA/'keyframes.json').read_text())['canvas']
    capture=cv2.VideoCapture(str(source));decoded=[]
    while True:
        ok,frame=capture.read()
        if not ok:break
        decoded.append(cv2.cvtColor(cv2.resize(frame,(width,height)),cv2.COLOR_BGR2GRAY))
    capture.release()
    frames=np.asarray(decoded)
    if len(frames)!=len(tracking['frames']):raise SystemExit('Source frame count changed')
    keymasks={int(p.stem):cv2.imread(str(p),cv2.IMREAD_GRAYSCALE) for p in (DATA/'keymasks').glob('*.png')}
    keys=sorted(keymasks)
    if keys[0]!=0 or keys[-1]!=len(frames)-1:raise SystemExit('Keymasks must cover the entire clip')
    if any(m is None or m.shape!=(height,width) for m in keymasks.values()):raise SystemExit('Invalid keymask dimensions')
    cv2.setNumThreads(2)
    flow=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    grid=np.dstack(np.meshgrid(np.arange(width,dtype=np.float32),np.arange(height,dtype=np.float32)))
    cache={}

    def propagate(mask,start,end):
        result=mask.astype(np.float32)
        step=1 if end>start else -1
        for i in range(start,end,step):
            j=i+step
            if (i,j) not in cache:cache[i,j]=flow.calc(frames[j],frames[i],None)
            field=cache[i,j]
            result=cv2.remap(result,grid[:,:,0]+field[:,:,0],grid[:,:,1]+field[:,:,1],
                             cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
        return result

    output=DATA/'masks';output.mkdir(exist_ok=True)
    for i in range(len(frames)):
        a=max(k for k in keys if k<=i);b=min(k for k in keys if k>=i)
        if a==b:mask=keymasks[a].astype(np.float32)
        else:
            fraction=(i-a)/(b-a)
            mask=propagate(keymasks[a],a,i)*(1-fraction)+propagate(keymasks[b],b,i)*fraction
        mask=np.clip((mask-112)*8,0,255).astype(np.uint8)
        mask=cv2.resize(mask,(960,540),interpolation=cv2.INTER_LINEAR)
        if not cv2.imwrite(str(output/f'{i}.png'),mask):raise SystemExit(f'Cannot write matte {i}')
    print(f'Baked {len(frames)} synchronized mattes from {len(keys)} reviewed keymasks')


if __name__=='__main__':main()
