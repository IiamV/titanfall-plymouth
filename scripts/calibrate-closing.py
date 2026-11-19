#!/usr/bin/env python3
"""Bake the authored overlay for every source frame; development tool only.

Normal builds read the baked PNGs and require neither OpenCV nor NumPy.
The contours retain source cockpit/shutter pixels and replace the outside view.
"""
import hashlib
import json
from pathlib import Path

DATA=Path(__file__).resolve().parents[1]/'theme/closing'


def main():
    try:
        import cv2
        import numpy as np
    except ImportError:
        raise SystemExit('Matte baking needs OpenCV and NumPy in a development environment; normal builds use the baked PNGs.')
    data=json.loads((DATA/'rotoscope.json').read_text())
    width,height=data['canvas'];output=tuple(data['output_canvas']);scale=4
    tracking=json.loads((DATA/'long/tracking.json').read_text())
    source=DATA.parents[1]/tracking['source']
    if hashlib.sha256(source.read_bytes()).hexdigest()!=tracking['source_sha256']:
        raise SystemExit('Source changed; wire matting requires the calibrated clip.')
    capture=cv2.VideoCapture(str(source))
    target=DATA/'masks';target.mkdir(exist_ok=True)
    for entry in data['frames']:
        ok,frame=capture.read()
        if not ok:raise SystemExit('Source ended before the last authored overlay')
        gray=cv2.cvtColor(cv2.resize(frame,(width,height)),cv2.COLOR_BGR2GRAY)
        # Recover the real cable's fine edge inside a continuous narrow band.
        # This retains source pixels, not a newly drawn cable. A soft contrast
        # matte avoids the on/off threshold that made earlier wires flicker.
        background=cv2.morphologyEx(gray,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))
        contrast=np.clip((background.astype(float)-gray)/28,0,1)
        contrast=cv2.resize(contrast,(width*scale,height*scale),interpolation=cv2.INTER_LINEAR)
        mask=np.zeros((height*scale,width*scale),np.uint8)
        def points(path):return np.rint(np.asarray(path)*scale).astype(np.int32)
        if entry['outline']:
            cv2.fillPoly(mask,[points(entry['outline'])],255,lineType=cv2.LINE_AA)
            for path,thickness in zip(entry['wires'],data['wire_widths']):
                band=np.zeros_like(mask)
                cv2.polylines(band,[points(path)],False,255,round((thickness+4)*scale),lineType=cv2.LINE_AA)
                keep=band.astype(float)*contrast
                center=np.zeros_like(mask)
                cv2.polylines(center,[points(path)],False,255,round(0.8*scale),lineType=cv2.LINE_AA)
                keep=np.maximum(keep,center)
                mask=np.minimum(mask,255-keep.astype(np.uint8))
            for path in entry['occluders']:
                cv2.fillPoly(mask,[points(path)],0,lineType=cv2.LINE_AA)
        mask=cv2.resize(mask,output,interpolation=cv2.INTER_AREA)
        if not cv2.imwrite(str(target/f'{entry["frame"]}.png'),mask):raise SystemExit('Cannot write mask')
    capture.release()
    print(f'Baked {len(data["frames"])} individual anti-aliased source-frame overlays')


if __name__=='__main__':main()
