#!/usr/bin/env python3
"""Check native 4:3 and ultrawide screenshots for full layout without a logo."""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT/"build/manifest.json").read_text())
bottom_bounds = manifest["panels"]["bottom"]["bounds"]

for width, height in [(1024, 768), (1280, 540)]:
    prefix = ROOT / f"build/plymouth-black-{width}x{height}"
    def image(suffix):
        return subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(prefix) + suffix,
                                        "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"])
    initial = image("-background.png")
    baseline = image("-screenshot.png")
    data = image("-closed.png")
    assert len(data) == len(baseline) == width * height * 3
    def ink(x, y):
        i = (y * width + x) * 3
        return max(abs(data[i+c] - baseline[i+c]) for c in range(3)) > 30
    # The packaged SDDM screenshot has its own white border, so compare edge
    # visibility directly; a difference from the background would be ambiguous.
    def visible(x, y):
        i = (y * width + x) * 3
        return min(data[i:i+3]) > 210
    for x in [0, width - 1]:
        assert sum(visible(x, y) for y in range(height)) > height * 0.9, "A side border was cropped"
    for y in [0, height - 1]:
        assert sum(visible(x, y) for x in range(width)) > width * 0.9, "A horizontal border was cropped"
    # This internal seam distinguishes responsive placement from a cropped
    # 16:9 image even when the backdrop supplies a matching outer border.
    seam_y = int(bottom_bounds[1] * height / 540)
    rows = [(y, [x for x in range(width//10, width*9//10) if ink(x, y)])
            for y in range(seam_y - 4, seam_y + 5)]
    _, seam = max(rows, key=lambda row: len(row[1]))
    assert len(seam) > bottom_bounds[2] * width/960 * 0.9, "The bottom seam is missing"
    # Compare the stroke's extents with a margin for its increased thickness.
    margin=7*width/960
    assert abs(min(seam)-bottom_bounds[0]*width/960)<=margin and abs(max(seam)-(bottom_bounds[0]+bottom_bounds[2])*width/960)<=margin, "The panel layout was cropped instead of resized"
    for y in range(int(145*height/540), int(320*height/540)):
        start = (y * width + int(390*width/960)) * 3
        end = (y * width + int(570*width/960)) * 3
        assert data[start:end] == baseline[start:end], "A logo remains in the main panel"
    assert all(max(initial[i:i+3])-min(initial[i:i+3])<=4 for i in range(0,len(initial),3)), "A picture is visible behind the initial fixed outlines"
    assert baseline != initial, "The assembled SDDM image is missing"
    print(f"{width}x{height}: uncropped panel borders, no logo, inward line entrance, assembled SDDM image")
