"""Extract the recorded shutter animation above a fixed cockpit/view."""
import json
import math
from pathlib import Path
import shutil
import subprocess

DATA=Path(__file__).resolve().parents[1]/'theme/closing'


def run(*args):subprocess.run([str(a) for a in args],check=True)


def sample(keys,seconds):
    if seconds<=keys[0][0]:return keys[0][1]
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if seconds<=b:return x+(y-x)*(seconds-a)/(b-a)
    return keys[-1][1]


def config():return json.loads((DATA/'layers.json').read_text())


def opacity(source,mask,target,gain=1):
    run('magick',source,'-evaluate','Multiply',gain,'-clamp',mask,'-alpha','off',
        '-compose','CopyOpacity','-composite','-background','black','-alpha','Background','PNG32:'+str(target))


def prepare(theme,prepared,speed):
    c=config();profile=prepared['sequence'];rate=30000/1001
    reference=c['reference_frames'][profile]['cockpit'];frames=prepared['frames'];masks=DATA/'layers'
    opacity(frames/f'{reference}.png',masks/'cockpit-mask.png',theme/'closing-cockpit.png')
    opacity(frames/f'{reference}.png',masks/'wire-mask.png',theme/'closing-wire.png')
    run('magick','-size','16x16','xc:black',theme/'closing-black.png')
    offset=c['source_time_offset'][profile];source_offset=c['global_source_offsets'][profile]
    duration=(c['source_end_time']-offset)/speed;count=math.ceil(duration*c['fps']-1e-8)
    first,last=c['recorded_first_frame'],c['recorded_last_frame']
    hold=6/rate if profile == "semi-long" else 0
    for part in ('top','bottom'):
        source_dir=theme/f'closing-source-{part}';source_dir.mkdir(exist_ok=True)
        for index,global_frame in enumerate(range(first,last+1)):
            local_frame=global_frame-source_offset
            gain=sample(prepared['occlusion']['fade'],local_frame/rate)
            opacity(frames/f'{local_frame}.png',masks/f'{part}-{global_frame}.png',source_dir/f'{index}.png',1/max(.1,gain))
        x,y,w,h=c['crop'][part]
        # FFmpeg carries alpha through the same motion compensation as RGB.
        # The perspective/size changes come from the movie, not PNG translation.
        filters=f'tpad=start_duration={hold}:stop_duration=1:start_mode=clone:stop_mode=clone,setpts=PTS/{speed},format=yuva444p,minterpolate=fps={c["fps"]}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,crop={w}:{h}:{x}:{y}'
        run('ffmpeg','-v','error','-y','-framerate','30000/1001','-i',source_dir/'%d.png',
            '-vf',filters,'-frames:v',count,'-start_number',0,'-pix_fmt','rgba',theme/f'closing-{part}-%d.png')
        shutil.rmtree(source_dir)
    return {'fps':c['fps'],'frames':count,'duration':count/c['fps'],
            'fade_start':max(0,(c['fade_start']-offset)/speed),'fade_end':max(0,(c['fade_end']-offset)/speed),
            'source_offset':offset,'source_first_frame':first-source_offset,'source_last_frame':last-source_offset,
            'crop':c['crop'],'representation':c['representation'],'source_sha256':prepared['sha256']}


def render(theme,target,layers,png=False):
    args=[]
    for name,moving in [('opening.png',False),('closing-bottom-%d.png',True),
                        ('closing-cockpit.png',False),('closing-wire.png',False),('closing-top-%d.png',True)]:
        if not moving:args+=['-loop',1]
        args+=['-framerate',layers['fps'],'-i',theme/name]
    bx,by,_,_=layers['crop']['bottom'];tx,ty,_,_=layers['crop']['top']
    filters=f'[0:v][1:v]overlay={bx}:{by}:format=rgb[a];[a][2:v]overlay=0:0:format=rgb[b];[b][3:v]overlay=0:0:format=rgb[c];[c][4:v]overlay={tx}:{ty}:format=rgb[d];[d]fade=t=out:st={layers["fade_start"]}:d={layers["fade_end"]-layers["fade_start"]}[out]'
    output=['-start_number',0,'-pix_fmt','rgb24'] if png else ['-c:v','libx264','-crf',16,'-pix_fmt','yuv420p','-movflags','+faststart']
    run('ffmpeg','-v','error','-y',*args,'-filter_complex',filters,'-map','[out]',
        '-frames:v',layers['frames'],*output,target)
