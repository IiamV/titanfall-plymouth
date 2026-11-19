#!/usr/bin/env python3
"""Draw lines inward, animate masked pictures, then retract lines outward."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import shutil
import subprocess
from sddm_background import SDDMImage, SDDMImageNotFound, find_sddm_image
from wallpaper import WallpaperNotFound, find_wallpaper
from images import validate_image
import full_sequence

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
LIGHTING = ROOT / "theme/lighting.json"
DEFAULT_SPEED = 1.25


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def ffmpeg(*args):
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args)


def hex_color(value):
    value = value.removeprefix("#")
    if not re.fullmatch(r"[0-9a-fA-F]{3}([0-9a-fA-F]{3})?",value):
        raise argparse.ArgumentTypeError("Use a hex color such as '#112233' or '#abc'")
    if len(value)==3: value="".join(c*2 for c in value)
    return "#"+value.lower()


def animation_speed(value):
    try: speed=float(value)
    except (ValueError,TypeError): raise argparse.ArgumentTypeError("Speed must be a number from 0.25 to 4")
    if not math.isfinite(speed) or not 0.25 <= speed <= 4:
        raise argparse.ArgumentTypeError("Speed must be from 0.25 to 4; the default is 1.25, lower is slower")
    return speed


def image_argument(value):
    try: return validate_image(value)
    except ValueError as error: raise argparse.ArgumentTypeError(str(error)) from error


def rgb(color):
    return tuple(int(color[i:i+2],16) for i in (1,3,5))


def scaled_config(speed):
    config=json.loads(LIGHTING.read_text())
    for panel in config["panels"].values():
        panel["keys"]=[[time/speed,value] for time,value in panel["keys"]]
    config["lines"]={key:value/speed for key,value in config["lines"].items()}
    return config


def audio_tempo(speed):
    filters=[]
    while speed<0.5: filters.append("atempo=0.5"); speed/=0.5
    while speed>2: filters.append("atempo=2"); speed/=2
    filters.append(f"atempo={speed}")
    return ",".join(filters)


def build(audio, background=None, panel_color=None, line_color=None, speed=DEFAULT_SPEED, sequence="short", opening_color=None, opening_picture=None):
    for command in ("ffmpeg", "ffprobe", "magick"):
        if not shutil.which(command):
            raise SystemExit(f"Missing dependency: {command}")
    if sequence not in ('short','full'): raise SystemExit('Sequence must be short or full')
    if sequence=='short' and (opening_color or opening_picture): raise SystemExit('Opening options require --sequence full')
    try: prepared=full_sequence.prepare(BUILD) if sequence=='full' else None
    except ValueError as error: raise SystemExit(str(error)) from error
    config = scaled_config(speed)
    source = ROOT / config["source"]
    required = [ROOT/name for name in ("machine-noise.m4a", "marauder-corps.m4a", "the-line.m4a")] if audio else []
    missing = [path.name for path in required if not path.is_file()]
    if missing and sequence=="short":
        raise SystemExit("Missing local audio: "+", ".join(missing)+". Omit --audio or restore your local audio files.")
    metadata = (json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "format=duration:stream=nb_frames", "-of", "json", str(source)], text=True)) if source.is_file() else None)
    reference_duration = float(metadata["format"]["duration"]) if metadata else config["reference_duration"]
    source_duration = reference_duration/speed
    fps = config["fps"]
    panels = config["panels"]
    if set(panels) != {"top", "left", "middle", "right", "bottom"}:
        raise SystemExit("The layout must include all five panels")
    for panel in panels.values():
        times = [time for time, _ in panel["keys"]]
        if times != sorted(set(times)) or times[-1] > source_duration:
            raise SystemExit("Invalid panel keyframe times")
        xs, ys = zip(*panel["polygon"])
        panel["bounds"] = [min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys)]
        rise = times[-1]-times[-2]
        panel["frames"] = math.ceil(rise*fps)+1 if any(panel["motion"]) else 1
    assembly_time = max(panel["keys"][-1][0] for panel in panels.values())
    line_in_start = config["lines"]["entrance_start"]
    line_in_duration = config["lines"]["entrance_duration"]
    line_in_end = line_in_start+line_in_duration
    line_out_start = assembly_time+config["lines"]["exit_delay"]
    line_out_duration = config["lines"]["exit_duration"]
    line_out_end = line_out_start+line_out_duration
    if min(panel["keys"][-2][0] for panel in panels.values()) < line_in_end:
        raise SystemExit("Pictures must wait until the inward line entrance finishes")
    duration = max(source_duration,line_out_end+config["blank_hold"])
    fit = "cover"
    setup = [f"fps = {fps};", f"assembly_time = {assembly_time};",
             f"line_in_start = {line_in_start};", f"line_in_duration = {line_in_duration};",
             f"line_out_start = {line_out_start};", f"line_out_duration = {line_out_duration};",
             f"line_frame_count = {math.ceil(line_in_duration*fps)+1};",
             f"panel_order = {json.dumps(list(panels))};"]
    for name, panel in panels.items():
        setup += [f'lighting["{name}"] = {json.dumps(panel["keys"])};',
                  f'bounds["{name}"] = {json.dumps(panel["bounds"])};',
                  f'frame_count["{name}"] = {panel["frames"]};']
    BUILD.mkdir(exist_ok=True)
    palettes = [("black", "#000000", "#ffffff"), ("white", "#ffffff", "#000000")]
    if panel_color or line_color:
        panel_color = panel_color or "#000000"
        automatic = "#000000" if sum(v*w for v,w in zip(rgb(panel_color),(0.2126,0.7152,0.0722)))>150 else "#ffffff"
        palettes = [("custom",panel_color,line_color or automatic)]
    intros={}
    for variant, bg, fg in palettes:
        output_variant=f"full-{variant}" if sequence=='full' else variant
        name = f"titanfall-{output_variant}"
        theme = BUILD / "themes" / name
        if theme.exists():
            shutil.rmtree(theme)  # Generated assets only.
        theme.mkdir(parents=True, exist_ok=True)
        if background:
            run("magick", str(background.path)+"[0]", "-background", bg, "-alpha", "remove",
                "-alpha", "off", "PNG24:"+str(theme / "background.png"))
            fitting = "scale=960:540:force_original_aspect_ratio=increase,crop=960:540"
            ffmpeg("-i", theme / "background.png", "-vf", fitting, "-frames:v", 1,
                   "-pix_fmt", "rgb24", theme / "assembled.png")
        else:
            run("magick", "-size", "960x540", f"xc:{bg}", "PNG24:"+str(theme / "assembled.png"))
        # Draw internal polygon edges only; no stroke follows the screen rim.
        segments = set()
        for panel in panels.values():
            points = panel["polygon"]
            for a, b in zip(points, points[1:]+points[:1]):
                if (a[0] == b[0] and a[0] in (0,960)) or (a[1] == b[1] and a[1] in (0,540)):
                    continue
                segments.add(tuple(sorted((tuple(a),tuple(b)))))
        # Drop partial duplicates at the middle/bottom junctions so every
        # uninterrupted seam has one midpoint and one pair of endpoints.
        def on_segment(point, a, b):
            return ((point[0]-a[0])*(b[1]-a[1]) == (point[1]-a[1])*(b[0]-a[0])
                    and min(a[0],b[0]) <= point[0] <= max(a[0],b[0])
                    and min(a[1],b[1]) <= point[1] <= max(a[1],b[1]))
        segments = sorted(segment for segment in segments if not any(
            segment != other and all(on_segment(point,*other) for point in segment)
            for other in segments))
        horizontal_traces = []
        for a,b in segments:
            if a[1] != b[1]: continue
            starts,ends = [],[]
            for point in (a,b):
                radius = max(abs(point[0]-480)/480,abs(point[1]-270)/270)
                delay = 1-radius
                starts.append(delay)
                ends.append(min(1,delay+abs(b[0]-a[0])/2/480))
            horizontal_traces.append({"endpoints":[a,b],"starts":starts,"ends":ends})
        trace_by_segment = {tuple(map(tuple,trace["endpoints"])):trace for trace in horizontal_traces}
        line_frames = math.ceil(line_in_duration*fps)+1
        for frame in range(line_frames):
            visible = frame/(line_frames-1)
            horizontal, others = [], []
            if frame:
                for a,b in segments:
                    if a[1] != b[1]:
                        others.append(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}"/>')
                        continue
                    # Only the middle-to-top and middle-to-bottom seams.
                    trace = trace_by_segment[(a,b)]
                    for side,(start,end) in enumerate(((a,b),(b,a))):
                        delay,finish = trace["starts"][side],trace["ends"][side]
                        progress = max(0,min(1,(visible-delay)/(finish-delay)))
                        if progress <= 0: continue
                        x = start[0]+(end[0]-start[0])*progress/2
                        horizontal.append(f'<line x1="{start[0]}" y1="{start[1]}" x2="{x}" y2="{start[1]}"/>')
            # Preserve the previous screen-centered wipe for all other seams.
            inset_x, inset_y = 480*visible,270*visible
            clips = [(0,0,960,inset_y),(0,540-inset_y,960,inset_y),
                     (0,inset_y,inset_x,540-2*inset_y),
                     (960-inset_x,inset_y,inset_x,540-2*inset_y)]
            rectangles = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}"/>'
                                 for x,y,w,h in clips if w>0 and h>0)
            outlines = theme / "lines.svg"
            outlines.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">'
                                '<defs><clipPath id="screen-wipe">'+rectangles+'</clipPath></defs>'
                                f'<g stroke="{fg}" stroke-width="6" stroke-linecap="butt">'
                                '<g clip-path="url(#screen-wipe)">'+"".join(others)+'</g>'+
                                "".join(horizontal)+'</g></svg>')
            run("magick", "-background", "none", outlines, "PNG32:"+str(theme / f"lines-{frame}.png"))
        shutil.copy2(theme / f"lines-{line_frames-1}.png",theme / "lines.png")
        for part, panel in panels.items():
            points = " ".join(f"{x},{y}" for x,y in panel["polygon"])
            mask_svg = theme / f"mask-{part}.svg"
            mask_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">'
                                '<rect width="960" height="540" fill="black"/>'
                                f'<polygon points="{points}" fill="white"/></svg>')
            mask = theme / f"mask-{part}.png"
            run("magick", mask_svg, mask)
            count = panel["frames"]
            progress = f"clip(T/{(count-1)/fps},0,1)" if count > 1 else "1"
            dx, dy = panel["motion"]
            sx, sy = f"clip(X-({dx})*(1-({progress})),0,W-1)", f"clip(Y-({dy})*(1-({progress})),0,H-1)"
            x,y,width,height = panel["bounds"]
            # Shift the picture sampling, THEN apply the fixed panel mask.
            # Borders and panel silhouettes never translate with the picture.
            shader = ":".join(f"{channel}='{channel}({sx},{sy})'" for channel in ("r","g","b"))
            ffmpeg("-loop", 1, "-framerate", fps, "-i", theme / "assembled.png",
                   "-loop", 1, "-framerate", fps, "-i", mask,
                   "-filter_complex", f"[0:v]format=rgb24,geq={shader}[picture];[1:v]format=gray[a];"
                   f"[picture][a]alphamerge,format=rgba,crop={width}:{height}:{x}:{y}[out]",
                   "-map", "[out]", "-frames:v", count, "-start_number", 0, theme / f"face-{part}-%d.png")
            shutil.copy2(theme / f"face-{part}-{count-1}.png", theme / f"face-{part}.png")
        run("magick", "-size", "16x16", f"xc:{bg}", theme / "panel.png")
        intro=full_sequence.compose(theme,prepared,speed,fps,opening_color or bg,opening_picture) if prepared else {'duration':0,'frames':0}
        intros[output_variant]=intro
        motion_setup=setup+[f"intro_duration = {intro['duration']};",f"intro_frame_count = {intro['frames']};"]
        script = (ROOT / "theme/titanfall.script").read_text()
        for token,value in {"@BG@":",".join(str(v/255) for v in rgb(bg)), "@FG@":",".join(str(v/255) for v in rgb(fg)),
                            "@MOTION_SETUP@":"\n".join(motion_setup)}.items():
            script = script.replace(token,value)
        (theme / f"{name}.script").write_text(script)
        descriptor = (ROOT / "theme/titanfall.plymouth").read_text().replace("titanfall",name)
        (theme / f"{name}.plymouth").write_text(descriptor.replace("Titanfall Pilot Link", f"Titanfall Pilot Link ({output_variant})"))
        inputs, filters = [], []
        previous = "0:v"
        for index,(part,panel) in enumerate(panels.items(), start=1):
            start,end = panel["keys"][-2][0],panel["keys"][-1][0]
            if panel["frames"] == 1:
                inputs += ["-loop",1,"-framerate",fps,"-i",theme / f"face-{part}-0.png"]
                padding = ""
            else:
                rate = (panel["frames"]-1)/(end-start)
                inputs += ["-framerate",f"{rate:.9f}","-i",theme / f"face-{part}-%d.png"]
                padding = f"tpad=start_duration={start}:start_mode=clone:stop_duration={duration}:stop_mode=clone,fps={fps},"
            progress = f"clip((T-{start})/{end-start},0,1)"
            ease = f"({progress})*({progress})*(3-2*({progress}))"
            filters.append(f"[{index}:v]{padding}format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='alpha(X,Y)*({ease})'[p{index}]")
            x,y,_,_ = panel["bounds"]
            filters.append(f"[{previous}][p{index}]overlay=x={x}:y={y}[s{index}]")
            previous = f"s{index}"
        full_index = len(panels)+1
        inputs += ["-loop",1,"-framerate",fps,"-i",theme / "assembled.png"]
        filters.append(f"[{previous}][{full_index}:v]overlay=x=0:y=0:enable='gte(t,{assembly_time})'[joined]")
        line_index = full_index+1
        timeline = BUILD / f"line-timeline-{variant}"
        if timeline.exists(): shutil.rmtree(timeline)
        timeline.mkdir()
        for tick in range(math.ceil(duration*fps)+1):
            seconds = tick/fps
            if seconds < line_in_end:
                visible = max(0,min(1,(seconds-line_in_start)/line_in_duration))
            else:
                visible = 1-max(0,min(1,(seconds-line_out_start)/line_out_duration))
            frame = int(visible*(line_frames-1)+0.5)
            (timeline / f"{tick}.png").symlink_to(theme / f"lines-{frame}.png")
        inputs += ["-framerate",fps,"-i",timeline / "%d.png"]
        filters.append(f"[{line_index}:v]format=rgba[borders]")
        filters.append("[joined][borders]overlay=0:0[out]")
        preview = BUILD / f"preview-{output_variant}.mp4"
        ffmpeg("-f","lavfi","-i",f"color=c={bg}:s=960x540:r={fps}:d={duration}",*inputs,
               "-filter_complex",";".join(filters),"-map","[out]","-an","-t",duration,
               "-c:v","libx264","-crf",16,"-pix_fmt","yuv420p","-movflags","+faststart",preview)
        if prepared: full_sequence.prepend(theme,preview,intro,fps)
        if audio:
            tempo=audio_tempo(speed)
            audio_inputs=[]
            audio_filters=[]
            labels=[]
            if not missing:
                audio_inputs += ["-i",ROOT/"machine-noise.m4a","-i",ROOT/"marauder-corps.m4a","-i",ROOT/"the-line.m4a"]
                for index,(delay,volume) in enumerate(((0,0.6),(300/speed,1),(2600/speed,1)),start=1):
                    audio_filters.append(f"[{index}:a]{tempo},volume={volume},adelay={round(delay+intro['duration']*1000)}:all=1[a{index}]")
                    labels.append(f"[a{index}]")
            if prepared:
                index=len(labels)+1
                audio_inputs += ['-i',prepared['source']]
                audio_filters.append(f"[{index}:a]{tempo}[closing]")
                labels.append('[closing]')
            audio_filters.append(''.join(labels)+f"amix=inputs={len(labels)}:normalize=0,alimiter=limit=0.9[mix]")
            ffmpeg('-i',preview,*audio_inputs,'-filter_complex',';'.join(audio_filters),'-map','0:v','-map','[mix]',
                   '-c:v','copy','-c:a','aac','-t',duration+intro['duration'],BUILD/f'preview-{output_variant}-audio.mp4')
        print(f"Built {name}: inward line entrance, picture slide/fade, outward line exit")
    manifest = {"source":config["source"],"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None,
                "source_duration":reference_duration,"source_frames":metadata["streams"][0].get("nb_frames") if metadata else None,"fps":fps,
                "sequence":sequence,"intro":intro,"intros":intros,"timeline_offset":intro["duration"],"speed":speed,"palettes":{(f"full-{v}" if sequence=="full" else v):{"panel":bg,"lines":fg} for v,bg,fg in palettes},
                "panels":panels,"mode":"inward-pictures-outward","assembly_time":assembly_time,
                "lines":{"animation":"horizontal-endpoints","frames":line_frames,"segments":segments,"horizontal_traces":horizontal_traces,**config["lines"],"entrance_end":line_in_end,"exit_start":line_out_start,"exit_end":line_out_end},
                "preview_duration":duration+intro["duration"],"short_duration":duration,"artwork":config["artwork"],
                "background":({"path":str(background.path),"theme":background.theme,"kind":background.kind,"fit":fit} if background else None)}
    encoded=json.dumps(manifest,indent=2)+"\n"
    (BUILD/"manifest.json").write_text(encoded)
    (BUILD/f"manifest-{sequence}.json").write_text(encoded)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence",choices=['short','full'],default='short',help='short light-up or full actual closing footage followed by light-up')
    opening=parser.add_mutually_exclusive_group()
    opening.add_argument('--opening-color',type=hex_color,help='color inside the marked cockpit opening (full sequence)')
    opening.add_argument('--opening-picture',type=image_argument,help='picture inside the marked cockpit opening (full sequence)')
    parser.add_argument("--audio",action="store_true",help="mix local audio files into MP4 previews")
    parser.add_argument("--panel-color",type=hex_color,help="hex backdrop/solid-panel color; creates the custom variant")
    parser.add_argument("--line-color",type=hex_color,help="hex seam color; creates the custom variant")
    parser.add_argument("--speed",type=animation_speed,default=DEFAULT_SPEED,help="animation speed multiplier, 0.25..4 (default: 1.25; lower is slower)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--background",type=image_argument,help="picture to cut into the fixed panel shapes")
    group.add_argument("--wallpaper",action="store_true",help="discover a user wallpaper or a standard-folder fallback")
    group.add_argument("--sddm-background",action="store_true")
    group.add_argument("--sddm-preview",action="store_true")
    args = parser.parse_args()
    background = None
    try:
        if args.background:
            path = args.background.expanduser().resolve()
            if not path.is_file(): parser.error(f"Background image not found: {path}")
            background = SDDMImage(path,"","custom wallpaper")
        elif args.wallpaper:
            detected=find_wallpaper()
            background=SDDMImage(detected.path,"",f"{detected.kind} wallpaper ({detected.source})")
        elif args.sddm_background or args.sddm_preview:
            background = find_sddm_image(preview=args.sddm_preview)
    except (SDDMImageNotFound,WallpaperNotFound) as error:
        parser.error(str(error))
    if background: print(f"Using {background.kind}: {background.path}",flush=True)
    build(args.audio,background,args.panel_color,args.line_color,args.speed,args.sequence,args.opening_color,args.opening_picture)
