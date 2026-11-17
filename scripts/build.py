#!/usr/bin/env python3
"""Build clean four-panel Plymouth animations using the complete local reference."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
MOTION = ROOT / "theme/motion.json"


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def ffmpeg(*args):
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args)


def motion_expression(keys):
    """The same piecewise linear motion used by the Plymouth sampler."""
    expression = str(keys[-1][1])
    for (start, first), (end, last) in reversed(list(zip(keys, keys[1:]))):
        segment = f"{first}+({last-first})*(t-{start})/{end-start}"
        expression = f"if(lt(t,{end}),{segment},{expression})"
    return f"if(lt(t,{keys[0][0]}),{keys[0][1]},{expression})"


def build(audio):
    for executable in ("ffmpeg", "ffprobe", "magick"):
        if not shutil.which(executable):
            raise SystemExit(f"Missing dependency: {executable}")
    motion = json.loads(MOTION.read_text())
    source = ROOT / motion["source"]
    metadata = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "format=duration:stream=nb_frames", "-of", "json", str(source)], text=True))
    source_duration = float(metadata["format"]["duration"])
    fps = motion["fps"]
    fade_start = source_duration + motion["fade_delay"]
    fade_duration = motion["fade_duration"]
    duration = fade_start + fade_duration + motion["blank_hold"]
    panels = motion["panels"]
    if set(panels) != {"left", "right", "top", "bottom"}:
        raise SystemExit("The motion definition must include all four panels")
    for panel in panels.values():
        times = [time for time, _ in panel["keys"]]
        if times != sorted(set(times)) or times[-1] > source_duration:
            raise SystemExit("Invalid panel keyframe times")
    setup = [f"fps = {fps};", f"fade_start = {fade_start};", f"fade_duration = {fade_duration};"]
    for name, panel in panels.items():
        setup.append(f'motion["{name}"] = {json.dumps(panel["keys"])};')
    BUILD.mkdir(exist_ok=True)
    for variant, bg, fg in (("black", "black", "white"), ("white", "white", "black")):
        name = f"titanfall-{variant}"
        theme = BUILD / "themes" / name
        if theme.exists():
            shutil.rmtree(theme)  # Generated output only; original media is untouched.
        theme.mkdir(parents=True, exist_ok=True)
        for part in panels:
            svg = (ROOT / f"theme/panels/{part}.svg").read_text()
            svg = svg.replace("@BG@", bg).replace("@FG@", fg)
            svg_path = theme / f"{part}.svg"
            svg_path.write_text(svg)
            run("magick", "-background", "none", svg_path, "PNG32:" + str(theme / f"{part}.png"))
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
        input_args = []
        # This order puts the top panel above both side plates and the bottom.
        for index, (part, panel) in enumerate(panels.items(), start=1):
            input_args += ["-loop", 1, "-framerate", fps, "-i", theme / f"{part}.png"]
            x, y = map(str, panel["base"])
            delta = motion_expression(panel["keys"])
            if panel["axis"] == "x":
                x += f"+({delta})"
            else:
                y += f"+({delta})"
            filters.append(f"[{index}:v]format=rgba,fade=t=out:st={fade_start}:d={fade_duration}:alpha=1[p{index}]")
            filters.append(f"[{previous}][p{index}]overlay=x='{x}':y='{y}':eval=frame[s{index}]")
            previous = f"s{index}"
        logo = motion["logo"]
        logo_index = len(panels) + 1
        input_args += ["-loop", 1, "-framerate", fps, "-i", theme / "marauder-logo.png"]
        logo_y = f'{logo["center"][1] - logo["size"]/2}+({motion_expression(panels["top"]["keys"])})'
        filters.append(f'[{logo_index}:v]scale={logo["size"]}:{logo["size"]},format=rgba,'
                       f'fade=t=out:st={fade_start}:d={fade_duration}:alpha=1[logo]')
        filters.append(f'[{previous}][logo]overlay=x={logo["center"][0] - logo["size"]/2}:'
                       f"y='{logo_y}':eval=frame:shortest=1[out]")
        preview = BUILD / f"preview-{variant}.mp4"
        ffmpeg("-f", "lavfi", "-i", f"color=c={bg}:s=960x540:r={fps}:d={duration}",
               *input_args, "-filter_complex", ";".join(filters), "-map", "[out]", "-an",
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
        print(f"Built {name}: four clean moving panels; logo attached to top panel")
    manifest = {"source": motion["source"], "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "source_duration": source_duration, "source_frames": metadata["streams"][0].get("nb_frames"),
                "fps": fps, "panels": panels, "logo": logo,
                "fade_start_seconds": fade_start, "fade_end_seconds": fade_start + fade_duration,
                "preview_duration": duration, "variants": ["black", "white"]}
    (BUILD / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", action="store_true", help="mix supplied audio for desktop previews only")
    build(parser.parse_args().audio)
