# Testing and maintenance

## How rendering works

`theme/lighting.json` defines the five panel masks, slide offsets, and base timings. The middle picture fades without sliding. Other picture cuts slide subtly inside fixed masks. Top and bottom activate faster than the sides.

Only the two horizontal seams beside the middle panel use endpoint-to-midpoint tracing. Each waits for the adjoining wipe to reach its endpoints. Other seams retain the screen-centered wipe; exit reverses the sequence.

The build precomputes picture and line frames. Native Plymouth and MP4 previews use those same assets. Selected colors, speed, timings, and image provenance appear in `build/manifest.json`. All animation times are divided by `--speed`; audio is time-scaled too when requested.

The picture fills a 960×540 canvas using aspect-preserving cover scaling and a centered crop. The completed canvas and panel layout resize with the display. Picture edges can be cropped at different aspect ratios. The completed snapshot replaces the individual cuts to avoid tiny alpha-edge seams.

Changing a wallpaper, palette, or speed requires rebuilding, copying the generated theme, and regenerating the initramfs. A snapshot cannot display a live SDDM greeter or follow desktop wallpaper changes automatically.

## Native tests

The preview runs in private user, mount, network, and PID namespaces. It does not select a system theme or modify the host daemon configuration. Headless previews require Xvfb and ImageMagick. Visible previews require X11 or XWayland.

```bash
python3 scripts/test-build-options.py
python3 scripts/test-sddm-background.py
python3 scripts/build.py --sddm-preview
bash scripts/preview-plymouth.sh --headless black
bash scripts/preview-plymouth.sh --headless white
python3 scripts/check-previews.py
bash scripts/preview-plymouth.sh --headless black 8 1024x768
bash scripts/preview-plymouth.sh --headless black 8 1280x540
python3 scripts/check-layouts.py
```

For a custom build, preview `custom` and use `python3 scripts/check-previews.py --variant custom`. The preview chooses a duration from the current manifest when seconds are omitted. Use a longer explicit duration if needed for a slow animation. A single build manifest describes the most recently generated variants.

For a synthetic prompt check:

```bash
bash scripts/preview-plymouth.sh --headless --diagnostics black 10
```

Do not enter a real password. This tests prompt rendering; physical displays and real encrypted-root unlocking need separate boot validation. If user namespaces are disabled, do not run preview commands against a live boot daemon.

A coordinate image helps verify picture motion and line exits against either palette:

```bash
mkdir -p .work
ffmpeg -hide_banner -loglevel error -f lavfi \
  -i "nullsrc=s=960x540,geq=r='X/W*255':g='Y/H*255':b='mod(7*X+11*Y,256)'" \
  -frames:v 1 -pix_fmt rgb24 -y .work/panel-texture-test.png
python3 scripts/build.py --background .work/panel-texture-test.png
bash scripts/preview-plymouth.sh --headless black
bash scripts/preview-plymouth.sh --headless white
python3 scripts/check-previews.py --check-texture-motion
```

Rebuild with the desired SDDM picture or wallpaper afterward.

## Optional audio and original media

Normal builds do not require the original video or logo. The reference duration is recorded in the layout configuration. If a local `closing-pilot.mp4` exists, its actual metadata and hash are recorded instead; it is never cut or overwritten. The logo is unused.

`--audio` requires local `machine-noise.m4a`, `marauder-corps.m4a`, and `the-line.m4a`. It generates `build/preview-<variant>-audio.mp4`; plain MP4s are silent. No boot-audio service is installed. Original media paths are ignored by Git and excluded from published history.

On the development machine, originals are saved in a local stash named `local original media and logo`. Find its index with `git stash list` and restore with `git stash apply 'stash@{N}'`. Applying preserves the stash backup. Stashes and the `local-original-history` backup branch are not pushed.

## Installation and rollback

The install commands in the README are for systems using `plymouth-set-default-theme -R`. Ensure the system already has the appropriate Plymouth initramfs hook and boot arguments, and verify regeneration succeeds before rebooting. The project does not change SDDM or desktop settings or delay boot to finish the animation.

Restore the previous theme:

```bash
sudo plymouth-set-default-theme -R "$(cat build/previous-theme.txt)"
```

Changes are saved in separate title-only conventional commits. Inspect a checkpoint without discarding current work:

```bash
git log --oneline
git switch -c inspect-checkpoint COMMIT_HASH
```

References: [Plymouth scripting](https://wiki.freedesktop.org/www/Software/Plymouth/Scripts/), [Plymouth overview](https://wiki.freedesktop.org/www/Software/Plymouth/).
