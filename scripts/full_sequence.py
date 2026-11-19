"""Composite the marked cockpit opening into actual local closing footage."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'theme/full'


def run(*command): subprocess.run([str(value) for value in command],check=True)


def interpolate(keys,seconds):
    if seconds<=keys[0][0]: return keys[0][1]
    for (start,a),(end,b) in zip(keys,keys[1:]):
        if seconds<=end:
            fraction=(seconds-start)/(end-start)
            def blend(a,b):
                if isinstance(a,list): return [blend(x,y) for x,y in zip(a,b)]
                return a+(b-a)*fraction
            return blend(a,b)
    return keys[-1][1]


def prepare(build_root):
    tracking=json.loads((DATA/'tracking.json').read_text())
    source=ROOT/tracking['source']
    if not source.is_file():
        raise ValueError('Full sequence requires the local long.mp4 reference. The short version does not need it.')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if digest!=tracking['source_sha256']:
        raise ValueError('long.mp4 differs from the calibrated closing clip. Restore the supplied reference so the opening mask stays aligned.')
    mattes=DATA/'masks'
    if len(list(mattes.glob('*.png')))!=len(tracking['frames']):
        raise ValueError('The calibrated full-sequence opening mattes are missing. Restore the repository assets before building Full.')
    frames=build_root/'full-source-frames'
    marker=frames/'source.sha256'
    if not marker.is_file() or marker.read_text()!=digest or len(list(frames.glob('*.png')))!=len(tracking['frames']):
        if frames.exists(): shutil.rmtree(frames)
        frames.mkdir(parents=True)
        run('ffmpeg','-hide_banner','-loglevel','error','-y','-i',source,'-map','0:v:0','-vf','scale=960:540',
            '-fps_mode','passthrough','-start_number',0,frames/'%d.png')
        marker.write_text(digest)
    return {'source':source,'sha256':digest,'frames':frames,'mattes':mattes,'tracking':tracking,
            'occlusion':json.loads((DATA/'occlusion.json').read_text())}


def compose(theme,prepared,speed,fps,color,picture=None):
    tracking=prepared['tracking']
    count=math.ceil(tracking['duration']/speed*fps)
    opening=theme/'opening.png'
    if picture:
        run('magick',str(picture)+'[0]','-background',color,'-alpha','remove','-alpha','off',
            '-resize','960x540^','-gravity','center','-extent','960x540','PNG24:'+str(opening))
    else: run('magick','-size','960x540',f'xc:{color}','PNG24:'+str(opening))
    reference=theme/'opening-mask.png'
    run('magick',DATA/'opening-mask.png','-resize','960x540!',reference)
    for frame in range(count):
        source_time=frame/fps*speed
        source_index=min(range(len(tracking['frames'])),key=lambda i:abs(tracking['frames'][i]['time']-source_time))
        source=prepared['frames']/f'{source_index}.png'
        entry=tracking['frames'][source_index]
        gain=interpolate(prepared['occlusion']['fade'],entry['time'])
        target=theme/f'intro-{frame}.png'
        mask=theme/f'intro-mask-{frame}.png'
        if gain<=0:
            shutil.copy2(source,target)
            run('magick','-size','960x540','xc:black',mask)
            continue
        shutil.copy2(prepared.get('mattes',DATA/'masks')/f'{source_index}.png',mask)
        run('magick',source,'(',opening,'-evaluate','Multiply',gain,mask,'-alpha','off','-compose','CopyOpacity',
            '-composite',')','-compose','Over','-composite','PNG24:'+str(target))
    return {'duration':count/fps,'frames':count,'source':str(prepared['source']),
            'source_sha256':prepared['sha256'],'opening':{'color':color,'picture':str(picture) if picture else None}}


def prepend(theme,preview,intro,fps):
    temporary=preview.with_name('tail-'+preview.name)
    preview.replace(temporary)
    prefix=preview.with_name('intro-'+preview.name)
    run('ffmpeg','-hide_banner','-loglevel','error','-y','-framerate',fps,'-i',theme/'intro-%d.png',
        '-frames:v',intro['frames'],'-c:v','libx264','-crf',16,'-pix_fmt','yuv420p',prefix)
    run('ffmpeg','-hide_banner','-loglevel','error','-y','-i',prefix,'-i',temporary,
        '-filter_complex','[0:v]setpts=PTS-STARTPTS[a];[1:v]setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0[out]',
        '-map','[out]','-c:v','libx264','-crf',16,'-pix_fmt','yuv420p','-movflags','+faststart',preview)
