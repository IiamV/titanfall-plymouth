#!/usr/bin/env python3
"""Verify fixed outlines, clipped fade-dominant pictures, and center-out line fill."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
W,H = 960,540


def pixels(path,fmt="rgb24"):
    return subprocess.check_output(["ffmpeg","-v","error","-i",str(path),"-pix_fmt",fmt,"-f","rawvideo","pipe:1"])


def probe_picture(part, phase, theme, panel, ink, background):
    regions = {"top":(400,50,550,100),"left":(65,300,150,420),"middle":(430,250,530,320),
               "right":(820,300,900,420),"bottom":(380,490,580,520)}
    x0,y0,width,height = panel["bounds"]
    x1,y1,x2,y2 = regions[part]
    samples = [(x,y) for y in range(y1,y2,13) for x in range(x1,x2,17) if not ink[y*W+x]]
    results = []
    for frame in range(panel["frames"]):
        face = pixels(theme/f"face-{part}-{frame}.png","rgba")
        pairs = []
        for x,y in samples:
            local=((y-y0)*width+x-x0)*4
            target=(y*W+x)*3
            if face[local+3] != 255: continue
            pairs += [(face[local+c]-background,phase[target+c]-background) for c in range(3)]
        denominator = sum(source*source for source,_ in pairs)
        alpha = sum(source*actual for source,actual in pairs)/denominator if denominator else 0
        error = sum(abs(actual-alpha*source) for source,actual in pairs)/len(pairs) if pairs else 999
        results.append((error,frame,alpha))
    error,frame,alpha = min(results)
    assert error < 1.2 and 0.05 < alpha < 0.95, f"{part}: picture is not partially fading in at its fixed position: {error=}, {alpha=}"
    if part == "middle":
        assert frame == 0 and panel["frames"] == 1 and panel["motion"] == [0,0], "Middle picture is sliding"
    else:
        assert 0 < frame < panel["frames"]-1, f"{part}: subtle picture movement is missing"
    print(f"  {part}: frame {frame}, opacity {alpha:.0%}, RGB error {error:.2f}" + (" (fade only)" if part == "middle" else " (small internal slide)"))


def line_strength(frame,photo,ink,foreground):
    values = {}
    for point,alpha in enumerate(ink):
        if alpha < 250: continue
        i=point*3
        channel=max(range(3),key=lambda c:abs(foreground-photo[i+c]))
        delta=foreground-photo[i+channel]
        if abs(delta)>80: values[point]=(frame[i+channel]-photo[i+channel])/delta
    return values


parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--variant",choices=["black","white"])
parser.add_argument("--check-texture-motion",action="store_true",help="fit fading and internal motion using the coordinate test picture")
args=parser.parse_args()
manifest=json.loads((ROOT/"build/manifest.json").read_text())
assert manifest["mode"] == "fixed-outlines-fade-textures"
panels=manifest["panels"]
assert set(panels)=={"top","left","middle","right","bottom"}
assert panels["middle"]["motion"]==[0,0] and panels["middle"]["frames"]==1
for part in ("top","bottom"):
    assert panels[part]["keys"][-1][0]-panels[part]["keys"][-2][0] < 0.3, "Top/bottom animation is not faster"
assert manifest["lines"]["fill_start"] >= manifest["assembly_time"]
for variant in ([args.variant] if args.variant else ["black","white"]):
    theme=ROOT/f"build/themes/titanfall-{variant}"
    prefix=ROOT/f"build/plymouth-{variant}"
    bg,fg=(0,255) if variant=="black" else (255,0)
    photo=pixels(theme/"assembled.png")
    line=pixels(theme/"lines.png","rgba")
    ink=line[3::4]
    initial=pixels(str(prefix)+"-background.png")
    active=[point for point in range(W*H) if any(initial[point*3+c]!=bg for c in range(3))]
    assert len(active)>1000 and all(ink[point] for point in active), "Initial frame contains moving borders or a picture behind the panels"
    masks={part:pixels(theme/f"mask-{part}.png") for part in panels}
    assert all(any(mask[i] for mask in masks.values()) for i in range(0,W*H*3,3)), "Panel layout has a hole"
    bottom=panels["bottom"]["bounds"]
    shared=sorted({x for x,y in panels["middle"]["polygon"] if y==bottom[1]})
    assert shared==[bottom[0],bottom[0]+bottom[2]], "Bottom width differs from the middle stem"
    # The former thin seams were about 2 pixels; the updated stem is >=4.
    assert sum(ink[400*W+x]>0 for x in range(320,345))>=4, "Outline thickness did not increase"
    for x in (40,100,170):
        y=40+100*x/215
        assert any(ink[row*W+x] for row in range(int(y)-10,int(y)+11)), "Side-to-top seam is not diagonal"
    for part,panel in panels.items():
        x0,y0,width,height=panel["bounds"]
        for frame in sorted({0,panel["frames"]//2,panel["frames"]-1}):
            face=pixels(theme/f"face-{part}-{frame}.png","rgba")
            for y in range(0,height,3):
                for x in range(0,width,11):
                    local=(y*width+x)*4
                    source=((y+y0)*W+x+x0)*3
                    assert abs(face[local+3]-masks[part][source])<=1, f"{part}: picture moved outside its fixed mask"
                    if frame==panel["frames"]-1 and face[local+3]==255:
                        assert max(abs(face[local+c]-photo[source+c]) for c in range(3))<=1, f"{part}: settled picture does not match screenshot"
        if args.check_texture_motion:
            probe_picture(part,pixels(str(prefix)+f"-phase-{part}.png"),theme,panel,ink,bg)
    closed=pixels(str(prefix)+"-closed.png")
    early=pixels(str(prefix)+"-line-early.png")
    late=pixels(str(prefix)+"-line-late.png")
    lit=pixels(str(prefix)+"-lit.png")
    strengths=[line_strength(frame,photo,ink,fg) for frame in (closed,early,late,lit)]
    median=sorted(strengths[0].values())[len(strengths[0])//2]
    assert abs(median-manifest["lines"]["idle_opacity"])<0.025, "Lines brightened before the pictures finished"
    bright=[{point for point,value in stage.items() if value>0.85} for stage in strengths[1:]]
    assert bright[0]<=bright[1]<=bright[2], "Line fill does not grow outward"
    def distance(point):
        x,y=point%W,point//W
        return max(abs(x-W/2)/(W/2),abs(y-H/2)/(H/2))
    # Black strokes on the installed dark screenshot have no measurable RGB
    # contrast in its center. The coordinate-image probe exercises both colors.
    central_contrast=sum(distance(point)<0.45 for point in strengths[0])
    if central_contrast>=100:
        assert len(bright[0])>100, "Center fill is missing"
        early_radius=max(map(distance,bright[0])); late_radius=max(map(distance,bright[1]))
        assert early_radius<0.65 and late_radius>early_radius+0.15, "Line fill is not centered and outward-moving"
    else:
        print(f"  {variant}: early center-fill RGB check needs a contrasting diagnostic image")
    assert len(bright[2])>=len(strengths[3])*0.98, "Outlines do not fill completely"
    changed=[point for point in range(W*H) if max(abs(lit[point*3+c]-photo[point*3+c]) for c in range(3))>3]
    assert changed and all(ink[point] for point in changed), "Outline geometry moved"
    assert pixels(str(prefix)+"-screenshot.png")==photo, "Final picture differs after outline fade"
    assert not (theme/"marauder-logo.png").exists()
    print(f"{variant}: diagonal seams, thicker fixed lines, clipped pictures, fade-only middle, center-out fill, final screenshot verified")
