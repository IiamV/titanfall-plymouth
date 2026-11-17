#!/usr/bin/env python3
"""Build generated cockpit panels with directional sliding light reveals."""
import argparse
import hashlib
import json
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
    for executable in ("ffmpeg", "ffprobe", "magick"):
        if not shutil.which(executable):
            raise SystemExit(f"Missing dependency: {executable}")
    lighting = json.loads(LIGHTING.read_text())
    source = ROOT / lighting["source"]
    metadata = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "format=duration:stream=nb_frames", "-of", "json", str(source)], text=True))
    source_duration = float(metadata["format"]["duration"])
    fps = lighting["fps"]
    fade_start = source_duration + lighting["fade_delay"]
    fade_duration = lighting["fade_duration"]
    duration = fade_start + fade_duration + lighting["blank_hold"]
    background_fit = "contain" if background and background.kind == "packaged theme screenshot" else "cover"
    panels = lighting["panels"]
    if set(panels) != {"left", "right", "top", "bottom"}:
        raise SystemExit("The lighting definition must include all four panels")
    for panel in panels.values():
        times = [time for time, _ in panel["keys"]]
        if times != sorted(set(times)) or times[-1] > source_duration:
            raise SystemExit("Invalid panel keyframe times")
    for panel in panels.values():
        xs, ys = zip(*panel["polygon"])
        panel["bounds"] = [min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys)]
    setup = [f"background_present = {1 if background else 0};", f'background_fit = "{background_fit}";', f"fps = {fps};", f"fade_start = {fade_start};", f"fade_duration = {fade_duration};"]
    for name, panel in panels.items():
        setup.append(f'lighting["{name}"] = {json.dumps(panel["keys"])};')
        setup.append(f'bounds["{name}"] = {json.dumps(panel["bounds"])};')
        setup.append(f'direction["{name}"] = "{panel["reveal"]}";')
    BUILD.mkdir(exist_ok=True)
    for variant, bg, fg in (("black", "black", "white"), ("white", "white", "black")):
        name = f"titanfall-{variant}"
        theme = BUILD / "themes" / name
        if theme.exists():
            shutil.rmtree(theme)  # Generated output only; original media is untouched.
        theme.mkdir(parents=True, exist_ok=True)
        for part, panel in panels.items():
            points = " ".join(f"{x},{y}" for x, y in panel["polygon"])
            svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">'
                   '<rect width="960" height="540" fill="black"/>'
                   f'<polygon points="{points}" fill="white"/></svg>')
            svg_path = theme / f"mask-{part}.svg"
            mask_path = theme / f"mask-{part}.png"
            svg_path.write_text(svg)
            run("magick", svg_path, mask_path)
            # Convert the generated monochrome drawing into neutral ink and
            # alpha. Thresholding removes paper grain without redrawing shapes.
            ffmpeg("-i", ROOT / lighting["artwork"], "-i", mask_path,
                   "-f", "lavfi", "-i", f"color=c={fg}:s=960x540:r={fps}",
                   "-filter_complex", "[0:v]scale=960:540,format=gray,"
                   "lut=y='if(lt(val,160),255,0)'[e];[1:v]format=gray[m];"
                   "[e][m]blend=all_mode=multiply[a];[2:v][a]alphamerge,format=rgba,"
                   f"crop={panel['bounds'][2]}:{panel['bounds'][3]}:{panel['bounds'][0]}:{panel['bounds'][1]}[out]",
                   "-map", "[out]", "-frames:v", 1, theme / f"{part}.png")
        if background:
            run("magick", str(background.path) + "[0]", "-background", bg,
                "-alpha", "remove", "-alpha", "off", "PNG24:" + str(theme / "background.png"))
        run("magick", ROOT / "marauder-logo.png", "PNG32:" + str(theme / "marauder-logo.png"))
        run("magick", "-size", "16x16", f"xc:{bg}", theme / "panel.png")
        script = (ROOT / "theme/titanfall.script").read_text()
        for token, value in {"@BG@": "0" if bg == "black" else "1",
                             "@FG@": "1" if fg == "white" else "0",
                             "@MOTION_SETUP@": "\n".join(setup)}.items():
            script = script.replace(token, value)
        (theme / f"{name}.script").write_text(script)
        descriptor = (ROOT / "theme/titanfall.plymouth").read_text()
        descriptor = descriptor.replace("titanfall", name).replace("Titanfall Pilot Link", f"Titanfall Pilot Link ({variant})")
        (theme / f"{name}.plymouth").write_text(descriptor)
        filters = []
        previous = "0:v"
        if background:
            if background_fit == "contain":
                filters.append("[0:v]scale=960:540:force_original_aspect_ratio=decrease,"
                               f"pad=960:540:(ow-iw)/2:(oh-ih)/2:color={bg},setsar=1[wallpaper]")
            else:
                filters.append("[0:v]scale=960:540:force_original_aspect_ratio=increase,"
                               "crop=960:540,setsar=1[wallpaper]")
            previous = "wallpaper"
        input_args = []
        # Reveal clips move across the ink; source geometry stays registered.
        for index, (part, panel) in enumerate(panels.items(), start=1):
            input_args += ["-loop", 1, "-framerate", fps, "-i", theme / f"{part}.png"]
            start = panel["keys"][1][0]
            rise = panel["keys"][-1][0] - start
            progress = f"clip((T-{start})/{rise},0,1)"
            condition = {"right": f"lt(X,W*({progress}))", "left": f"gte(X,W*(1-({progress})))",
                         "down": f"lt(Y,H*({progress}))", "up": f"gte(Y,H*(1-({progress})))"}[panel["reveal"]]
            filters.append(f"[{index}:v]format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
                           f"a='alpha(X,Y)*({condition})',"
                           f"fade=t=out:st={fade_start}:d={fade_duration}:alpha=1[p{index}]")
            x, y, _, _ = panel["bounds"]
            filters.append(f"[{previous}][p{index}]overlay=x={x}:y={y}[s{index}]")
            previous = f"s{index}"
        logo = lighting["logo"]
        logo_index = len(panels) + 1
        input_args += ["-loop", 1, "-framerate", fps, "-i", theme / "marauder-logo.png"]
        top_start = panels["top"]["keys"][1][0]
        top_rise = panels["top"]["keys"][-1][0] - top_start
        x, y, _, height = panels["top"]["bounds"]
        logo_x = logo["center"][0] - logo["size"]/2
        logo_y = logo["center"][1] - logo["size"]/2
        front = f"{height}*clip((T-{top_start})/{top_rise},0,1)-{logo_y-y}"
        filters.append(f'[{logo_index}:v]scale={logo["size"]}:{logo["size"]},format=rgba,'
                       f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='alpha(X,Y)*lt(Y,({front}))',"
                       f'fade=t=out:st={fade_start}:d={fade_duration}:alpha=1[logo]')
        filters.append(f'[{previous}][logo]overlay=x={logo_x}:y={logo_y}:shortest=1[out]')
        preview = BUILD / f"preview-{variant}.mp4"
        backdrop_args = (["-loop", 1, "-framerate", fps, "-i", theme / "background.png"] if background else
                         ["-f", "lavfi", "-i", f"color=c={bg}:s=960x540:r={fps}:d={duration}"])
        ffmpeg(*backdrop_args, *input_args, "-filter_complex", ";".join(filters), "-map", "[out]", "-an",
               "-t", duration, "-c:v", "libx264", "-crf", 16, "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", preview)
        if audio:
            ffmpeg("-i", preview, "-i", ROOT / "machine-noise.m4a",
                   "-i", ROOT / "marauder-corps.m4a", "-i", ROOT / "the-line.m4a",
                   "-filter_complex", "[1:a]volume=0.6[a];[2:a]adelay=300:all=1[b];"
                   "[3:a]adelay=2600:all=1[c];"
                   "[a][b][c]amix=inputs=3:normalize=0,alimiter=limit=0.9[mix]",
                   "-map", "0:v", "-map", "[mix]", "-c:v", "copy", "-c:a", "aac",
                   "-t", duration, "-movflags", "+faststart", BUILD / f"preview-{variant}-audio.mp4")
        print(f"Built {name}: directional light-up; centered narrow bottom panel")
    manifest = {"source": lighting["source"], "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "source_duration": source_duration, "source_frames": metadata["streams"][0].get("nb_frames"),
                "fps": fps, "panels": panels, "logo": logo, "mode": "directional-light-up",
                "artwork": lighting["artwork"], "artwork_sha256": hashlib.sha256((ROOT / lighting["artwork"]).read_bytes()).hexdigest(),
                "fade_start_seconds": fade_start, "fade_end_seconds": fade_start + fade_duration,
                "preview_duration": duration, "variants": ["black", "white"],
                "background": ({"path": str(background.path), "theme": background.theme,
                                "kind": background.kind, "fit": background_fit} if background else None)}
    (BUILD / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", action="store_true", help="mix supplied audio for desktop previews only")
    backgrounds = parser.add_mutually_exclusive_group()
    backgrounds.add_argument("--background", type=Path, help="copy a custom wallpaper behind transparent panel outlines")
    backgrounds.add_argument("--sddm-background", action="store_true", help="discover and copy the active installed SDDM theme background")
    backgrounds.add_argument("--sddm-preview", action="store_true", help="discover and copy the active SDDM theme's packaged screenshot")
    args = parser.parse_args()
    background = None
    try:
        if args.background:
            path = args.background.expanduser().resolve()
            if not path.is_file():
                parser.error(f"Background image not found: {path}")
            background = SDDMImage(path, "", "custom wallpaper")
        elif args.sddm_background or args.sddm_preview:
            background = find_sddm_image(preview=args.sddm_preview)
    except SDDMImageNotFound as error:
        parser.error(str(error))
    if background:
        print(f"Using {background.kind}: {background.path}", flush=True)
    build(args.audio, background)
