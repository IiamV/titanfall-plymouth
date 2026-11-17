#!/usr/bin/env python3
"""Check fixed panel geometry, full coverage, sequential lighting, and final fade."""
import json
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 960, 540


def pixels(path):
    data = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path),
                                    "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"])
    assert len(data) == WIDTH * HEIGHT * 3, f"Unexpected image size: {path}"
    return data


def active(data, baseline):
    return {i for i in range(0, len(data), 3)
            if max(abs(data[i+c] - baseline[i+c]) for c in range(3)) > 8}


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--variant", choices=["white", "black"], help="check one palette, useful when matching image contrast")
args = parser.parse_args()
manifest = json.loads((ROOT / "build/manifest.json").read_text())
assert manifest["mode"] == "directional-light-up"
for variant in ([args.variant] if args.variant else ["white", "black"]):
    baseline = pixels(ROOT / f"build/plymouth-{variant}-background.png")
    masks = {name: pixels(ROOT / f"build/themes/titanfall-{variant}/mask-{name}.png")
             for name in ("left", "right", "top", "bottom")}
    assert all(any(mask[i] for mask in masks.values())
               for i in range(0, WIDTH * HEIGHT * 3, 3)), "Panel coverage has a hole"
    bottom_bounds = manifest["panels"]["bottom"]["bounds"]
    top_polygon = manifest["panels"]["top"]["polygon"]
    shared_x = sorted({x for x, y in top_polygon if y == bottom_bounds[1]})
    assert shared_x == [bottom_bounds[0], bottom_bounds[0] + bottom_bounds[2]], "Bottom width differs from the middle panel"
    closed = pixels(ROOT / f"build/plymouth-{variant}-closed.png")
    final_geometry = active(closed, baseline)
    for part, mask in masks.items():
        phase = pixels(ROOT / f"build/plymouth-{variant}-phase-{part}.png")
        lit = active(phase, baseline)
        assert sum(bool(mask[i]) for i in lit) > 30, f"{variant}: {part} never lights up"
        # Illumination may change intensity, but must not create edges at new
        # coordinates. This fails if panels slide or rotate into their positions.
        assert len(lit - final_geometry) <= 30, f"{variant}: {part} geometry moved"
        if part == "left":
            own_lit = {i for i in lit if mask[i]}
            own_final = {i for i in final_geometry if mask[i]}
            assert len(own_final - own_lit) > 50, "Left panel appeared all at once instead of wiping in"
            full_strength = sum(max(abs(phase[i+c] - closed[i+c]) for c in range(3)) <= 2
                                for i in own_lit)
            assert full_strength / len(own_lit) > 0.8, "Light-up is a uniform opacity fade instead of a sliding reveal"
    for y in range(145, 320):
        start, end = (y * WIDTH + 390) * 3, (y * WIDTH + 570) * 3
        assert closed[start:end] == baseline[start:end], "A logo is still drawn in the main panel"
    assert not (ROOT / f"build/themes/titanfall-{variant}/marauder-logo.png").exists()
    if manifest.get("background"):
        candidates = []
        for i in range(0, len(baseline), 3):
            rgb = baseline[i:i+3]
            x, y = (i//3) % WIDTH, (i//3) // WIDTH
            if max(rgb)-min(rgb) > 24 and not (410 < x < 550 and 160 < y < 305):
                candidates.append(i)
        if len(candidates) > 100:
            preserved = sum(closed[i:i+3] == baseline[i:i+3] for i in candidates)
            assert preserved / len(candidates) > 0.75, "Panel faces are obscuring the background"
    final = pixels(ROOT / f"build/plymouth-{variant}-screenshot.png")
    assert final == baseline, f"{variant}: background is not restored after the final fade"
    print(f"{variant}: full coverage, matching bottom width, sliding reveal, no logo, final fade verified")
