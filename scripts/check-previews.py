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


def emblem(data, baseline):
    colored = set()
    for y in range(145, 320):
        for x in range(390, 570):
            i = (y * WIDTH + x) * 3
            rgb = data[i:i+3]
            if max(rgb) - min(rgb) > 24 and any(abs(data[i+c] - baseline[i+c]) > 8 for c in range(3)):
                colored.add((x, y))
    assert colored, "The central/top-panel emblem is missing"
    center_x = (min(x for x, _ in colored) + max(x for x, _ in colored)) / 2
    center_y = (min(y for _, y in colored) + max(y for _, y in colored)) / 2
    assert abs(center_x - 480) <= 3 and abs(center_y - 234) <= 3, (
        f"Emblem is not centered on the main/top panel: {center_x}, {center_y}")
    return colored


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
        if part == "top":
            assert emblem(phase, baseline) == emblem(closed, baseline), f"{variant}: emblem position changed"
    for x, y in emblem(closed, baseline):
        assert masks["top"][(y * WIDTH + x) * 3], "Emblem falls outside the main/top panel"
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
    print(f"{variant}: full coverage, matching bottom width, sliding reveal, fixed emblem, final fade verified")
