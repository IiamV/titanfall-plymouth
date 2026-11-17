#!/usr/bin/env python3
"""Build fixed cockpit borders, fade-dominant picture motion, and center-out line fill."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
from sddm_background import SDDMImage, SDDMImageNotFound, find_sddm_image

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
LIGHTING = ROOT / "theme/lighting.json"


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def ffmpeg(*args):
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args)


def build(audio, background=None):
    for command in ("ffmpeg", "ffprobe", "magick"):
        if not shutil.which(command):
            raise SystemExit(f"Missing dependency: {command}")
    config = json.loads(LIGHTING.read_text())
    source = ROOT / config["source"]
    metadata = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "format=duration:stream=nb_frames", "-of", "json", str(source)], text=True))
    source_duration = float(metadata["format"]["duration"])
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
    fill_start = assembly_time + config["lines"]["fill_delay"]
    fill_duration = config["lines"]["fill_duration"]
    idle = config["lines"]["idle_opacity"]
    fade_start = max(source_duration + config["fade_delay"], fill_start+fill_duration)
    fade_duration = config["fade_duration"]
    duration = fade_start+fade_duration+config["blank_hold"]
    fit = "contain" if background and background.kind == "packaged theme screenshot" else "cover"
    setup = [f"fps = {fps};", f"assembly_time = {assembly_time};", f"fill_start = {fill_start};",
             f"fill_duration = {fill_duration};", f"line_idle = {idle};", f"fade_start = {fade_start};",
             f"fade_duration = {fade_duration};", f"panel_order = {json.dumps(list(panels))};"]
    for name, panel in panels.items():
        setup += [f'lighting["{name}"] = {json.dumps(panel["keys"])};',
                  f'bounds["{name}"] = {json.dumps(panel["bounds"])};',
                  f'frame_count["{name}"] = {panel["frames"]};']
    BUILD.mkdir(exist_ok=True)
    for variant, bg, fg in (("black", "black", "white"), ("white", "white", "black")):
        name = f"titanfall-{variant}"
        theme = BUILD / "themes" / name
        if theme.exists():
            shutil.rmtree(theme)  # Generated assets only.
        theme.mkdir(parents=True, exist_ok=True)
        if background:
            run("magick", str(background.path)+"[0]", "-background", bg, "-alpha", "remove",
                "-alpha", "off", "PNG24:"+str(theme / "background.png"))
            fitting = (f"scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:color={bg}"
                       if fit == "contain" else "scale=960:540:force_original_aspect_ratio=increase,crop=960:540")
            ffmpeg("-i", theme / "background.png", "-vf", fitting, "-frames:v", 1,
                   "-pix_fmt", "rgb24", theme / "assembled.png")
        else:
            run("magick", "-size", "960x540", f"xc:{bg}", "PNG24:"+str(theme / "assembled.png"))
        # One full-canvas outline image is always registered at the origin.
        ffmpeg("-i", ROOT / config["artwork"], "-f", "lavfi", "-i", f"color=c={fg}:s=960x540",
               "-filter_complex", "[0:v]scale=960:540,format=gray,lut=y='if(lt(val,160),255,0)'[a];"
               "[1:v][a]alphamerge,format=rgba[out]", "-map", "[out]", "-frames:v", 1, theme / "lines.png")
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
        script = (ROOT / "theme/titanfall.script").read_text()
        for token,value in {"@BG@":"0" if bg == "black" else "1", "@FG@":"1" if fg == "white" else "0",
                            "@MOTION_SETUP@":"\n".join(setup)}.items():
            script = script.replace(token,value)
        (theme / f"{name}.script").write_text(script)
        descriptor = (ROOT / "theme/titanfall.plymouth").read_text().replace("titanfall",name)
        (theme / f"{name}.plymouth").write_text(descriptor.replace("Titanfall Pilot Link", f"Titanfall Pilot Link ({variant})"))
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
        inputs += ["-loop",1,"-framerate",fps,"-i",theme / "lines.png"]
        filters.append(f"[{line_index}:v]format=rgba,split=2[dim_src][fill_src]")
        filters.append(f"[dim_src]colorchannelmixer=aa={idle},fade=t=out:st={fade_start}:d={fade_duration}:alpha=1[dim]")
        p = f"clip((T-{fill_start})/{fill_duration},0,1)"
        condition = f"lte(abs(X-W/2),W/2*({p}))*lte(abs(Y-H/2),H/2*({p}))"
        filters.append(f"[fill_src]geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='alpha(X,Y)*({condition})',fade=t=out:st={fade_start}:d={fade_duration}:alpha=1[bright]")
        filters += ["[joined][dim]overlay=0:0[outlined]", "[outlined][bright]overlay=0:0[out]"]
        preview = BUILD / f"preview-{variant}.mp4"
        ffmpeg("-f","lavfi","-i",f"color=c={bg}:s=960x540:r={fps}:d={duration}",*inputs,
               "-filter_complex",";".join(filters),"-map","[out]","-an","-t",duration,
               "-c:v","libx264","-crf",16,"-pix_fmt","yuv420p","-movflags","+faststart",preview)
        if audio:
            ffmpeg("-i",preview,"-i",ROOT/"machine-noise.m4a","-i",ROOT/"marauder-corps.m4a","-i",ROOT/"the-line.m4a",
                   "-filter_complex","[1:a]volume=0.6[a];[2:a]adelay=300:all=1[b];[3:a]adelay=2600:all=1[c];[a][b][c]amix=inputs=3:normalize=0,alimiter=limit=0.9[mix]",
                   "-map","0:v","-map","[mix]","-c:v","copy","-c:a","aac","-t",duration,BUILD/f"preview-{variant}-audio.mp4")
        print(f"Built {name}: fixed thick lines, fade-dominant pictures, center-out line fill")
    manifest = {"source":config["source"],"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
                "source_duration":source_duration,"source_frames":metadata["streams"][0].get("nb_frames"),"fps":fps,
                "panels":panels,"mode":"fixed-outlines-fade-textures","assembly_time":assembly_time,
                "lines":{**config["lines"],"fill_start":fill_start},"fade_start_seconds":fade_start,
                "fade_end_seconds":fade_start+fade_duration,"preview_duration":duration,"artwork":config["artwork"],
                "background":({"path":str(background.path),"theme":background.theme,"kind":background.kind,"fit":fit} if background else None)}
    (BUILD/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio",action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--background",type=Path,help="picture to cut into the fixed panel shapes")
    group.add_argument("--sddm-background",action="store_true")
    group.add_argument("--sddm-preview",action="store_true")
    args = parser.parse_args()
    background = None
    try:
        if args.background:
            path = args.background.expanduser().resolve()
            if not path.is_file(): parser.error(f"Background image not found: {path}")
            background = SDDMImage(path,"","custom wallpaper")
        elif args.sddm_background or args.sddm_preview:
            background = find_sddm_image(preview=args.sddm_preview)
    except SDDMImageNotFound as error:
        parser.error(str(error))
    if background: print(f"Using {background.kind}: {background.path}",flush=True)
    build(args.audio,background)
