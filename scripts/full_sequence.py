"""Composite the marked cockpit opening into actual local closing footage."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import layered_closing

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'theme/closing'
PROFILES={'long':'long-new.mp4','semi-long':'semi-long.mp4'}


def normalize(sequence):
    return 'long' if sequence=='full' else sequence


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


def prepare(build_root,sequence='long'):
    sequence=normalize(sequence)
    if sequence not in PROFILES: raise ValueError('Closing sequence must be long or semi-long')
    tracking=json.loads((DATA/sequence/'tracking.json').read_text())
    source=ROOT/tracking['source']
    if not source.is_file():
        raise ValueError(f'{sequence.title()} requires the local {tracking["source"]} reference. Short does not need it.')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if digest!=tracking['source_sha256']:
        raise ValueError(f'{tracking["source"]} differs from the calibrated clip. Restore the supplied reference so the opening stays aligned.')
    mattes=DATA/'masks'
    if any(not (mattes/f'{entry["mask"]}.png').is_file() for entry in tracking['frames']):
        raise ValueError('The calibrated opening mattes are missing. Restore the repository assets before building this sequence.')
    frames=build_root/f'{sequence}-source-frames'
    marker=frames/'source.sha256'
    if not marker.is_file() or marker.read_text()!=digest or len(list(frames.glob('*.png')))!=len(tracking['frames']):
        if frames.exists(): shutil.rmtree(frames)
        frames.mkdir(parents=True)
        run('ffmpeg','-hide_banner','-loglevel','error','-y','-i',source,'-map','0:v:0','-vf','scale=960:540',
            '-fps_mode','passthrough','-start_number',0,frames/'%d.png')
        marker.write_text(digest)
    return {'source':source,'sha256':digest,'frames':frames,'mattes':mattes,'tracking':tracking,
            'occlusion':{'fade':tracking['fade']},'sequence':sequence}


def playback_plan(tracking,speed,tail_fps):
    rate=tracking.get('source_rate',[tail_fps,1])
    source_fps=rate[0]/rate[1]
    end=tracking.get('playback_end_frame',len(tracking['frames']))
    if not isinstance(end,int) or not 1<=end<=len(tracking['frames']):
        raise ValueError('Invalid closing playback endpoint')
    source_duration=end/source_fps if 'source_rate' in tracking else tracking['duration']
    # Keep every source frame at the default speed. A separate clock lets
    # Short retain its existing 24 fps without decimating the cockpit movie.
    fps=min(60,max(source_fps,source_fps*speed))
    count=math.ceil(source_duration/speed*fps-1e-8)
    entries=tracking['frames'][:end]
    indices=[min(range(end),key=lambda i:abs(entries[i]['time']-frame/fps*speed)) for frame in range(count)]
    return {'fps':fps,'frames':count,'duration':count/fps,'source_indices':indices,
            'source_duration':source_duration,'source_end_frame':end,
            'trimmed_frames':len(tracking['frames'])-end}


def native_plan(intro,tail_fps):
    """Bound PNG decoding to 30 fps while preserving preview timestamps."""
    fps=min(30,intro.get('fps',tail_fps))
    count=math.ceil(intro['duration']*fps-1e-8) if intro['frames'] else 0
    indices=[min(intro['frames']-1,int(i*intro['fps']/fps+1e-8)) for i in range(count)]
    return fps,count,indices


def compose(theme,prepared,speed,fps,color,picture=None):
    tracking=prepared['tracking']
    full_plan=playback_plan(tracking,speed,fps)
    profile=prepared.get('sequence')
    extracted=profile in PROFILES
    prefix_end=layered_closing.config()['prefix_end_frame'][profile] if extracted else None
    if extracted and not prefix_end:
        plan={'fps':60,'frames':0,'duration':0,'source_indices':[]}
    else:
        movie_tracking={**tracking,'playback_end_frame':prefix_end} if extracted else tracking
        plan=playback_plan(movie_tracking,speed,fps)
    count=plan['frames'];fps=plan['fps']
    opening=theme/'opening.png'
    if picture:
        run('magick',str(picture)+'[0]','-background',color,'-alpha','remove','-alpha','off',
            '-resize','960x540^','-gravity','center','-extent','960x540','PNG24:'+str(opening))
    else: run('magick','-size','960x540',f'xc:{color}','PNG24:'+str(opening))
    camera=json.loads((DATA/'camera.json').read_text())['frames'] if profile=='long' and picture else None
    moving=theme/'opening-moving.png'
    for frame in range(count):
        source_index=plan['source_indices'][frame]
        source=prepared['frames']/f'{source_index}.png'
        entry=tracking['frames'][source_index]
        gain=interpolate(prepared['occlusion']['fade'],entry['time'])
        target=theme/f'intro-{frame}.png'
        mask=theme/f'intro-mask-{frame}.png'
        if gain<=0:
            shutil.copy2(source,target)
            run('magick','-size','960x540','xc:black',mask)
            continue
        shutil.copy2(prepared.get('mattes',DATA/'masks')/f'{entry["mask"]}.png',mask)
        view=opening
        if camera:
            pose=camera[source_index]
            transform=f"480,270 {pose['cover_scale']} {pose['angle']} {480+pose['x']*1.5},{270+pose['y']*1.5}"
            run('magick',opening,'-virtual-pixel','edge','-define','distort:viewport=960x540+0+0',
                '-distort','SRT',transform,'+repage',moving)
            view=moving
        run('magick',source,'(',view,'-evaluate','Multiply',gain,mask,'-alpha','off','-compose','CopyOpacity',
            '-composite',')','-compose','Over','-composite','PNG24:'+str(target))
    if moving.exists():moving.unlink()
    if extracted:
        raw_indices=plan['source_indices']
        if count:
            smooth=theme/'smooth-prefix';smooth.mkdir(exist_ok=True)
            smooth_count=math.ceil(plan['duration']*60-1e-8)
            run('ffmpeg','-v','error','-y','-framerate',plan['fps'],'-i',theme/'intro-%d.png',
                '-vf','tpad=stop_duration=0.2:stop_mode=clone,format=yuv444p,minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1',
                '-frames:v',smooth_count,'-start_number',0,'-pix_fmt','rgb24',smooth/'%d.png')
            for old in list(theme.glob('intro-*.png')):old.unlink()
            for frame in range(smooth_count):(smooth/f'{frame}.png').replace(theme/f'intro-{frame}.png')
            smooth.rmdir()
            plan.update(fps=60,frames=smooth_count,duration=smooth_count/60,
                        source_indices=[min(prefix_end-1,round(i/60*speed*30000/1001)) for i in range(smooth_count)])
        layers=layered_closing.prepare(theme,prepared,speed)
        movie_duration=plan['duration'];total_duration=movie_duration+layers['duration']
        # Bake the authored layers once. Plymouth decodes one opaque frame per
        # refresh instead of blending six large sprites during boot.
        closing_dir=theme/'baked-closing';closing_dir.mkdir(exist_ok=True)
        layered_closing.render(theme,closing_dir/'%d.png',layers,png=True)
        movie_count=plan['frames']
        for i in range(layers['frames']):(closing_dir/f'{i}.png').replace(theme/f'intro-{movie_count+i}.png')
        closing_dir.rmdir()
        plan.update(frames=movie_count+layers['frames'],source_indices=list(range(movie_count+layers['frames'])))

        checkpoints={'start':0,'moving':min(total_duration-.05,(88*1001/30000/speed) if count else .1/speed),
                     'closing':movie_duration+max(0,(22*1001/30000-layers['source_offset'])/speed),
                     'black':movie_duration+layers['fade_end']+.04}
        return {**full_plan,**plan,'duration':total_duration,'movie_duration':movie_duration,
                'movie_frames':movie_count,'raw_source_indices':raw_indices,'layers':layers,'camera_tracking':bool(camera),
                'source_duration':full_plan['source_duration'],'source_end_frame':full_plan['source_end_frame'],
                'trimmed_frames':full_plan['trimmed_frames'],'source':str(prepared['source']),
                'source_sha256':prepared['sha256'],'checkpoints':checkpoints,
                'opening':{'color':color,'picture':str(picture) if picture else None}}
    checkpoints={'start':0}
    checkpoints.update({label:min(count-1,round(tracking['frames'][index]['time']/speed*fps))/fps
                        for label,index in tracking.get('checkpoints',{}).items()})
    return {**plan,'source':str(prepared['source']),'checkpoints':checkpoints,
            'source_sha256':prepared['sha256'],'opening':{'color':color,'picture':str(picture) if picture else None}}


def prepend(theme,preview,intro,fps):
    temporary=preview.with_name('tail-'+preview.name)
    preview.replace(temporary)
    segments=[]
    if intro['frames']:
        prefix=preview.with_name('intro-'+preview.name)
        run('ffmpeg','-hide_banner','-loglevel','error','-y','-framerate',intro['fps'],'-i',theme/'intro-%d.png',
            '-frames:v',intro['frames'],'-c:v','libx264','-crf',16,'-pix_fmt','yuv420p',prefix)
        segments.append(prefix)
    segments.append(temporary)
    inputs=[];filters=[];labels=[]
    for index,path in enumerate(segments):
        inputs+=['-i',path];filters.append(f'[{index}:v]setpts=PTS-STARTPTS[v{index}]');labels.append(f'[v{index}]')
    filters.append(''.join(labels)+f'concat=n={len(segments)}:v=1:a=0[out]')
    run('ffmpeg','-hide_banner','-loglevel','error','-y',*inputs,
        '-filter_complex',';'.join(filters),
        '-map','[out]','-fps_mode','vfr','-c:v','libx264','-crf',16,'-pix_fmt','yuv420p','-movflags','+faststart',preview)
