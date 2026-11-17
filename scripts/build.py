#!/usr/bin/env python3
"""Trace the reference cockpit closure into black/white Plymouth line art."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
FPS = 24
DURATION = 6
MOTION_START = 0.6
MOTION_DURATION = 0.8
FADE_START = 1.65
FADE_DURATION = 0.8


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def ffmpeg(*args):
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args)


def interpolate(t, points):
    for (a, x), (b, y) in zip(points, points[1:]):
        if t <= b:
            return x + (y - x) * max(0, (t - a) / (b - a))
    return points[-1][1]


def aperture_mask(t):
    # Measured from 28.6–29.4 s of the supplied reference. Only the opening
    # is masked: the actual cockpit/hatch contours come from the video pixels.
    top = interpolate(t, [(0, 38), (.2, 75), (.4, 149), (.6, 242), (.8, 342)])
    bottom = interpolate(t, [(0, 490), (.2, 429), (.4, 367), (.6, 327), (.8, 310)])
    opening = ""
    if bottom > top:
        opening = (f'<path fill="black" d="M250 {top + 8} L674 {top + 8} '
                   f'L659 {bottom - 8} L306 {bottom - 8} Z"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">'
            '<rect width="960" height="540" fill="white"/>' + opening + '</svg>')


def build(audio):
    for executable in ("ffmpeg", "magick"):
        if not shutil.which(executable):
            raise SystemExit(f"Missing dependency: {executable}")
    BUILD.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cockpit-trace-", dir=BUILD) as temporary:
        temp = Path(temporary)
        # Normalize before edge detection so the source's exposure fade does
        # not erase panel details. No gameplay colors or background are shown.
        ffmpeg("-i", ROOT / "assets/cockpit-close-reference.mp4", "-t", MOTION_DURATION,
               "-an", "-vf", f"fps={FPS},scale=960:540,normalize=independence=0:smoothing=0,"
               "edgedetect=low=0.06:high=0.16:mode=wires", "-start_number", 0, temp / "edge-%d.png")
        edges = sorted(temp.glob("edge-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
        if len(edges) < 2:
            raise SystemExit("Reference segment produced fewer than two frames")
        # Freeze exposure-stable contours into independent physical layers.
        # Chassis: original open cockpit. Upper/lower: actual moving hatch poses.
        masks = {
            "chassis": (0, aperture_mask(0)),
            "upper-panel": (10, '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540"><rect width="960" height="540" fill="black"/><path fill="white" d="M238 0 H716 L694 190 L278 190 Z"/></svg>'),
            "lower-panel": (10, '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540"><rect width="960" height="540" fill="black"/><path fill="white" d="M334 348 L638 348 L682 540 H296 Z"/></svg>'),
        }
        for layer, (_, svg) in masks.items():
            mask = temp / f"{layer}.svg"
            mask.write_text(svg)
            run("magick", mask, temp / f"{layer}-mask.png")
        for variant, bg, fg in (("black", "black", "white"), ("white", "white", "black")):
            name = f"titanfall-{variant}"
            theme = BUILD / "themes" / name
            # This directory is generated; remove obsolete assets from older builds.
            if theme.exists():
                shutil.rmtree(theme)
            theme.mkdir(parents=True, exist_ok=True)
            for layer, (index, _) in masks.items():
                ffmpeg("-i", edges[index], "-i", temp / f"{layer}-mask.png",
                       "-f", "lavfi", "-i", f"color=c={fg}:s=960x540:r={FPS}",
                       "-filter_complex", "[0:v]format=gray[e];[1:v]format=gray[m];"
                       "[e][m]blend=all_mode=multiply,lut=y='min(val*2.5,255)'[a];"
                       "[2:v][a]alphamerge,format=rgba[out]", "-map", "[out]",
                       "-frames:v", 1, theme / f"{layer}.png")
            # The supplied .png is actually WebP; Plymouth needs a real PNG.
            run("magick", ROOT / "marauder-logo.png", "PNG32:" + str(theme / "marauder-logo.png"))
            run("magick", "-size", "16x16", f"xc:{bg}", theme / "panel.png")
            script = (ROOT / "theme/titanfall.script").read_text()
            replacements = {"@BG@": "0" if bg == "black" else "1",
                            "@FG@": "1" if fg == "white" else "0",
                            "@FRAME_COUNT@": str(len(edges))}
            for token, value in replacements.items():
                script = script.replace(token, value)
            (theme / f"{name}.script").write_text(script)
            descriptor = (ROOT / "theme/titanfall.plymouth").read_text()
            descriptor = descriptor.replace("titanfall", name).replace("Titanfall Pilot Link", f"Titanfall Pilot Link ({variant})")
            (theme / f"{name}.plymouth").write_text(descriptor)
            # Native and video previews use the same three sprites and motion.
            travel = f"min(1,max(0,(t-{MOTION_START})/{MOTION_DURATION}))"
            filters = (
                f"[1:v]format=rgba,fade=t=in:st=0:d=0.35:alpha=1,fade=t=out:st={FADE_START}:d={FADE_DURATION}:alpha=1[chassis];"
                f"[2:v]format=rgba,fade=t=out:st={FADE_START}:d={FADE_DURATION}:alpha=1[upper];"
                f"[3:v]format=rgba,fade=t=out:st={FADE_START}:d={FADE_DURATION}:alpha=1[lower];"
                "[0:v][chassis]overlay=x=0:y=0[a];"
                f"[a][upper]overlay=x=0:y='-210+320*({travel})':eval=frame[b];"
                f"[b][lower]overlay=x=0:y='190-260*({travel})':eval=frame[c];"
                "[4:v]scale=151:151,format=rgba,fade=t=in:st=0.25:d=0.35:alpha=1,"
                f"fade=t=out:st={FADE_START}:d={FADE_DURATION}:alpha=1[logo];"
                "[c][logo]overlay=x=(W-w)/2:y=(H-h)/2:shortest=1[out]"
            )
            preview = BUILD / f"preview-{variant}.mp4"
            ffmpeg("-f", "lavfi", "-i", f"color=c={bg}:s=960x540:r={FPS}:d={DURATION}",
                   "-loop", 1, "-framerate", FPS, "-i", theme / "chassis.png",
                   "-loop", 1, "-framerate", FPS, "-i", theme / "upper-panel.png",
                   "-loop", 1, "-framerate", FPS, "-i", theme / "lower-panel.png",
                   "-loop", 1, "-framerate", FPS, "-i", theme / "marauder-logo.png",
                   "-filter_complex", filters, "-map", "[out]", "-an", "-t", DURATION,
                   "-c:v", "libx264", "-crf", 16, "-pix_fmt", "yuv420p", "-movflags", "+faststart", preview)
            if audio:
                ffmpeg("-i", preview, "-i", ROOT / "machine-noise.m4a",
                       "-i", ROOT / "marauder-corps.m4a", "-i", ROOT / "the-line.m4a",
                       "-filter_complex", "[1:a]volume=0.6[a];[2:a]adelay=300:all=1[b];"
                       "[3:a]adelay=2600:all=1[c];"
                       "[a][b][c]amix=inputs=3:normalize=0,alimiter=limit=0.9[mix]",
                       "-map", "0:v", "-map", "[mix]", "-c:v", "copy", "-c:a", "aac",
                       "-t", DURATION, "-movflags", "+faststart", BUILD / f"preview-{variant}-audio.mp4")
            print(f"Built {name}: independent sliding hatch sprites, {preview}")
        (BUILD / "manifest.json").write_text(json.dumps({"fps": FPS, "variants": ["black", "white"],
            "reference_start_seconds": 28.6, "reference_motion_seconds": MOTION_DURATION,
            "mechanism_layers": ["chassis", "upper-panel", "lower-panel"], "close_seconds": MOTION_START + MOTION_DURATION,
            "fade_start_seconds": FADE_START, "fade_end_seconds": FADE_START + FADE_DURATION}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", action="store_true", help="mix supplied audio for desktop previews only")
    build(parser.parse_args().audio)
