# Titanfall Plymouth

A Titanfall-inspired Plymouth splash that lights up a cockpit made from your SDDM screenshot or wallpaper. Lines draw inward, the picture pieces slide and fade into fixed panels, then the lines retract outward to leave the completed image.

## Demo

### Black variant

![Black variant: inward line drawing, panel lighting, and outward line removal](docs/demo/black.gif)

[Watch or download the black demo with audio](docs/demo/black-audio.mp4).

### White variant

![White variant: inward line drawing, panel lighting, and outward line removal](docs/demo/white.gif)

[Watch or download the white demo with audio](docs/demo/white-audio.mp4).

These demos use the installed WarGames theme's packaged SDDM screenshot. The GIFs loop silently; the MP4s include the supplied audio mix. Boot audio is not implemented. The picture is a static snapshot whose individual cuts animate during the sequence; it is not a live login screen.

## Animation

Five **fixed** cockpit shapes cut the selected SDDM screenshot or wallpaper into an expanded top header, left and right sides, a middle panel, and the narrow bottom panel. Side-to-top seams are continuous diagonals; the middle-to-top seam stays horizontal. Only internal seams are drawn; there is no outer screen border or logo.

- The thicker outlines stay in place. Only the two horizontal seams between the middle panel and the top/bottom panels draw from their endpoints toward their midpoint, then retract from their midpoint toward their endpoints. Each horizontal seam waits until the adjoining wipe reaches its endpoints, then draws at the wipe’s horizontal speed. The shorter bottom seam completes first; the exit reverses this sequence. All diagonal and vertical seams retain the screen-centered inward/outward wipe.
- The middle picture only fades in, with zero movement.
- Other pictures mostly fade, with small movement **inside their fixed masks**: 24 pixels on the sides, 12 on top, 6 on the bottom at the reference resolution.
- Top and bottom finish in 0.22 and 0.20 seconds; side fades take 0.55 seconds and the middle fade takes 0.70 seconds.
- Inward line drawing runs from 0.10 to 0.95 seconds. Pictures appear from 1.05 to 2.50 seconds; outward line removal runs from 2.65 to 3.50 seconds.

The header is enlarged by shortening the middle and side panels. The bottom width matches the middle panel's lower stem. Black and white variants control the empty-screen and outline colors; the screenshot keeps its colors. For the installed dark WarGames picture, use the black variant with white outlines.

The full screenshot is hidden until the individual pictures finish appearing. It then replaces their face layers to avoid alpha-edge rounding seams. The fixed outlines retract outward after the picture assembly; the completed screenshot remains for the login-screen handoff. A packaged SDDM screenshot is static, with noninteractive example controls.

## Build and review before installation

Dependencies: Python 3, FFmpeg, ImageMagick, and Plymouth with its script plugin.

The original media and logo are excluded from the published repository and its history. The ready-made demos above can be viewed without them. To build, supply your own `closing-pilot.mp4` at the repository root. Audio previews also require `machine-noise.m4a`, `marauder-corps.m4a`, and `the-line.m4a`. These paths are ignored by Git. The logo is unused.

On the development machine, the originals are saved in the local Git stash named `local original media and logo`. Find it with `git stash list` and restore it with `git stash apply 'stash@{N}'`, using its actual index. Applying keeps the stash backup. Stashes are not pushed.

```bash
python3 scripts/build.py --audio --sddm-preview
ffplay -autoexit build/preview-black-audio.mp4
ffplay -autoexit build/preview-white-audio.mp4
```

The build uses the active installed SDDM theme's packaged screenshot. On the inspected machine this is `/usr/share/sddm/themes/WarGames/preview.png`. Its configured `Background.png` is plain black, so the packaged preview makes image-piece motion easier to see.

Other image choices:

```bash
python3 scripts/build.py --audio --sddm-background
python3 scripts/build.py --audio --background /absolute/path/to/wallpaper.jpg
```

Without an image option, panel faces use the selected solid palette. `--audio` creates sound mixes in `preview-black-audio.mp4` and `preview-white-audio.mp4`. The plain `preview-black.mp4` and `preview-white.mp4` files are silent. Plymouth boot audio has not been implemented; no boot-audio service is installed.

Find installed SDDM images without building:

```bash
python3 scripts/sddm_background.py
python3 scripts/sddm_background.py --preview
```

Discovery reads standard SDDM configuration locations, respects theme directories and configuration overrides, and checks the active theme under `/usr/share/sddm/themes` or `/usr/local/share/sddm/themes`. Screenshots come from the theme metadata's `Screenshot` entry, with common packaged preview filenames as fallbacks. A missing image reports the theme and checked paths, then exits with an error instead of choosing an unrelated image.

## Layout and timing

The [generated panel artwork](theme/panels/generated-panels-v3.png) and [its prompt](theme/panels/generation-prompt-v3.txt) were the silhouette reference. Internal seams are now drawn directly from the panel polygons, excluding all edges along the screen rim. `theme/lighting.json` records the five masks, small internal picture offsets, fade times, and inward entrance and outward exit timing. The entire 5.44-second local video remains the timing reference; original media is never trimmed or overwritten.

The snapshot fills the 960×540 assembly canvas before cutting. Both packaged SDDM screenshots and wallpapers use aspect-preserving cover scaling with a centered crop; no palette-colored letterbox or side padding is added. Different aspect ratios can crop the picture edges. The complete canvas and all panel coordinates resize with the screen. The responsive layout is checked at 4:3 and ultrawide sizes.

Plymouth runs before the graphical login session; it cannot show a live SDDM window underneath its rendering. This implementation assembles a build-time image snapshot instead. Repeat the build, copy, and initramfs steps after changing the selected image. Neither SDDM nor desktop settings are modified. See the [official Plymouth overview](https://wiki.freedesktop.org/www/Software/Plymouth/) for its early-boot role.

## Test native Plymouth without installing

The preview uses private user, mount, network, and PID namespaces. Its theme and daemon configuration are visible only inside the preview process. The selected system theme and initramfs are not changed.

Visible preview requires X11 or XWayland:

```bash
bash scripts/preview-plymouth.sh black 8
bash scripts/preview-plymouth.sh white 8
```

Headless checks require Xvfb (Arch/CachyOS package `xorg-server-xvfb`):

```bash
bash scripts/preview-plymouth.sh --headless black 8
bash scripts/preview-plymouth.sh --headless white 8
python3 scripts/check-previews.py
bash scripts/preview-plymouth.sh --headless black 8 1024x768
bash scripts/preview-plymouth.sh --headless black 8 1280x540
python3 scripts/check-layouts.py
python3 scripts/test-sddm-background.py
```

`build/` stores the blank starting frame, inward line drawing stages, partial-picture captures, full outlines, outward line removal stages, and the final screenshot. The checks verify fixed masks and outline coordinates, thicker diagonal seams, zero middle movement, faster top/bottom timing, endpoint-to-midpoint drawing and midpoint-to-endpoint removal on both horizontal seams, absence of a logo, and exact final screenshot reconstruction. Picture pixels cannot escape their panel masks. The exit-direction check needs a contrasting image; black lines on a dark SDDM picture are verified using the diagnostic picture instead. Responsive checks verify proportional internal seam placement and absence of an outer border. Discovery tests cover configuration precedence, overrides, packaged screenshots, and missing files.

A stronger optional RGB probe uses a diagnostic coordinate image. It measures partial opacity, identifies the subtly shifted picture frame inside each fixed mask, and verifies the middle uses its single unshifted frame. It also checks outward removal against a contrasting picture:

```bash
mkdir -p .work
ffmpeg -hide_banner -loglevel error -f lavfi \
  -i "nullsrc=s=960x540,geq=r='X/W*255':g='Y/H*255':b='mod(7*X+11*Y,256)'" \
  -frames:v 1 -pix_fmt rgb24 -y .work/panel-texture-test.png
python3 scripts/build.py --background .work/panel-texture-test.png
bash scripts/preview-plymouth.sh --headless black 8
python3 scripts/check-previews.py --variant black --check-texture-motion

# Restore the real SDDM image before installation or ordinary review.
python3 scripts/build.py --audio --sddm-preview
```

Optional synthetic password-prompt check:

```bash
bash scripts/preview-plymouth.sh --headless --diagnostics black 10
```

Do not enter a real password during this diagnostic. It tests prompt rendering, not encrypted-root unlocking. Rerun normal headless previews before checking image reconstruction because diagnostic final frames deliberately contain a prompt. If user namespaces are disabled, `unshare` reports an error; do not run preview controls against a live boot daemon as a workaround.

## Install only after reviewing

No system installation has been performed. Choose one variant:

```bash
plymouth-set-default-theme > build/previous-theme.txt
sudo cp -r build/themes/titanfall-black /usr/share/plymouth/themes/
sudo plymouth-set-default-theme -R titanfall-black
```

Substitute `titanfall-white` in both installation commands for the other palette. The inspected CachyOS setup already has the `plymouth` mkinitcpio hook and `quiet splash`; this project changes neither. Check that initramfs regeneration succeeds before rebooting. Fast boots may finish before the animation completes; the theme does not delay startup. Desktop previews cannot validate firmware graphics, physical monitor layout, or real encrypted-root unlocking.

Restore the previous theme:

```bash
sudo plymouth-set-default-theme -R "$(cat build/previous-theme.txt)"
```

## Files and checkpoints

`build/manifest.json` records source hashes, timing, image selection, and panel bounds. `face-<panel>-<frame>.png` assets contain the small internal picture shifts under fixed masks. `face-<panel>.png` is the settled cut. `lines.png` is the complete internal outline image. Precomputed `lines-<frame>.png` assets animate only the two horizontal middle-panel seams along their length. Other seams retain the screen-centered wipe. The frames run in reverse for the exit. Native Plymouth and video demos use the same line frames. Generated build output is ignored by Git; the shareable GIF and audio MP4 demos are tracked in `docs/demo/`. The original logo is kept locally with the source media and is not loaded or copied into the theme.

Implementation follows the [Plymouth script reference](https://wiki.freedesktop.org/www/Software/Plymouth/Scripts/) and installed examples. Changes use separate title-only conventional commits:

```bash
git log --oneline
git switch -c inspect-checkpoint COMMIT_HASH
```
