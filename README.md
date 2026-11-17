# Titanfall SDDM panel assembly for Plymouth

The selected SDDM screenshot or wallpaper is cut into four cockpit-shaped image pieces. Those textured pieces slide into place in the staggered order of the light-up sequence in the complete local `closing-pilot.mp4`. The image pixels move with each piece: the full screenshot is not displayed behind arriving panels. No logo is drawn.

The left and right pieces extend to the screen bottom. The bottom piece has the same width as the middle panel's lower edge. Black and white variants control the empty-screen color and contrasting outlines; the screenshot keeps its original colors.

Once all pieces meet, their complete image replaces the individual face sprites to avoid alpha-edge rounding seams. This completed-image layer is hidden until assembly finishes. The outlines fade together after the full reference duration; the assembled screenshot remains for the login-screen handoff. A packaged screenshot is static and has no interactive login controls.

## Build and review before installation

Dependencies: Python 3, FFmpeg, ImageMagick, and Plymouth with its script plugin.

```bash
python3 scripts/build.py --audio --sddm-preview
ffplay -autoexit build/preview-black.mp4
ffplay -autoexit build/preview-white.mp4
```

The build uses the active installed SDDM theme's packaged screenshot. On the inspected machine this is `/usr/share/sddm/themes/WarGames/preview.png`. Its configured `Background.png` is plain black, so the packaged preview makes image-piece motion easier to see.

Other image choices:

```bash
python3 scripts/build.py --audio --sddm-background
python3 scripts/build.py --audio --background /absolute/path/to/wallpaper.jpg
```

Without an image option, panel faces use the selected solid palette. Optional sound mixes are saved as `build/preview-black-audio.mp4` and `build/preview-white-audio.mp4`; Plymouth itself is silent.

Find installed SDDM images without building:

```bash
python3 scripts/sddm_background.py
python3 scripts/sddm_background.py --preview
```

Discovery reads standard SDDM configuration locations, respects theme directories and configuration overrides, and checks the active theme under `/usr/share/sddm/themes` or `/usr/local/share/sddm/themes`. Screenshots come from the theme metadata's `Screenshot` entry, with common packaged preview filenames as fallbacks. A missing image reports the theme and checked paths, then exits with an error instead of choosing an unrelated image.

## Layout and timing

The [generated panel artwork](theme/panels/generated-panels-v2.png) and [its prompt](theme/panels/generation-prompt-v2.txt) define the silhouettes. `theme/lighting.json` records panel masks, slide directions, and arrival times. The entire 5.44-second local video remains the timing reference; original media is never trimmed or overwritten.

The snapshot is fitted to the 960×540 assembly canvas before cutting: packaged SDDM screenshots are contained without cropping, while wallpapers cover the canvas. The complete canvas and all panel coordinates resize with the screen. The responsive layout is checked at 4:3 and ultrawide sizes.

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

`build/` stores the blank initial frame, individual mid-slide captures, the assembled frame, and the final frame after outlines fade. The checks verify that each face PNG contains the correct screenshot pixels under its polygon mask, no complete image is visible initially, the bottom width matches the center, no logo is drawn, and the final frame exactly reconstructs the fitted screenshot. Responsive checks verify visible borders and proportional panel placement. Discovery tests cover configuration precedence, overrides, packaged screenshots, and missing files.

A stronger optional RGB-motion probe uses a diagnostic coordinate image. It matches translated texture pixels on **every** moving piece; uniform fading or an unmoving masked image fails this check:

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

`build/manifest.json` records source hashes, timing, image selection, and panel bounds. `face-<panel>.png` assets are the actual screenshot cuts; `<panel>.png` assets are their independent outlines. Generated output is ignored by Git. The supplied original logo remains in the repository but is not loaded or copied into the theme.

Implementation follows the [Plymouth script reference](https://wiki.freedesktop.org/www/Software/Plymouth/Scripts/) and installed examples. Changes use separate title-only conventional commits:

```bash
git log --oneline
git switch -c inspect-checkpoint COMMIT_HASH
```
