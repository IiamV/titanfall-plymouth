# Testing and maintenance

## How rendering works

`theme/lighting.json` defines the five panel masks, slide offsets, and base timings. The middle picture fades without sliding. Other picture cuts slide subtly inside fixed masks. Top and bottom activate faster than the sides.

Only the two horizontal seams beside the middle panel use endpoint-to-midpoint tracing. Each waits for the adjoining wipe to reach its endpoints. Other seams retain the screen-centered wipe; exit reverses the sequence.

The build precomputes picture and line frames. Native Plymouth and MP4 previews use those same assets. Selected colors, speed, timings, and image provenance appear in `build/manifest.json`. All animation times are divided by `--speed`; audio is time-scaled too when requested.

The picture fills a 960×540 canvas using aspect-preserving cover scaling and a centered crop. The completed canvas and panel layout resize with the display. Picture edges can be cropped at different aspect ratios. The completed snapshot replaces the individual cuts to avoid tiny alpha-edge seams.

Changing a wallpaper, palette, or speed requires rebuilding, copying the generated theme, and regenerating the initramfs. A snapshot cannot display a live SDDM greeter or follow desktop wallpaper changes automatically.

## Interactive CLI

Run `./install.sh`. Arrow keys (or j/k and Enter) choose options in a terminal; numbered menus work with redirected input. The picture menu has three choices: **SDDM**, **Picture**, and **Custom**. SDDM shows the detected screenshot path; Picture shows a discovered user wallpaper or a clearly marked default-folder fallback. The build uses the exact displayed path. Custom prompts for another file; blank input selects solid panels. Missing SDDM images are marked as not found and reported when selected. Custom colors and speed use the same validation as the build CLI. The default is 1.25×; slower presets are 1× and 0.75×. Custom speed accepts finite numbers from 0.25 to 4 and retries invalid input. Blank custom-speed input uses the default.

Custom picture validation expands `~` and environment variables, accepts quoted paths and local `file://` URIs, checks that a readable image file exists, and decodes its first frame with ImageMagick. Missing files, directories, empty/corrupt files, unsupported formats, remote URLs, control characters, and unmatched quotes are rejected. Decoder validation has a five-second timeout. Blank input at the optional custom-picture prompt still selects solid panels.

`./install.sh --preview-only` builds and offers the video preview without offering system installation. The settings and repeatable build command are saved in `build/setup-options.json`; build output goes to `build/setup-build.log`.

Installation reads the current theme and backs up any existing target theme under `build/install-backups/` before privileged writes. `build/install-history.json` records rollback information. A failed install attempts to restore the old assets and selection; if restoration fails, the saved history remains available for `./install.sh --restore`. Keep this checkout and its `build/` directory until rollback is no longer needed. Restoring changes the active theme and restores overwritten files; unused newly copied assets may remain in the theme directory.

Automatic installation needs `plymouth-set-default-theme -R`; use build/preview mode and your distribution's installation procedure if that tool is unavailable. The wizard does not install dependencies, change boot arguments, or reboot.

## Wallpaper discovery

```bash
python3 scripts/wallpaper.py
python3 scripts/wallpaper.py --json
python3 scripts/build.py --wallpaper --panel-color '#0b1220' --line-color '#6ee7ff'
```

Discovery tries running swww/awww and Hyprpaper queries first, then the active GNOME/Cinnamon/MATE or Xfce session. It then checks saved Hyprpaper, Sway/swaybg, Waypaper, KDE Plasma, Xfce, feh, Nitrogen, and pywal configuration. Active-desktop configs take priority over other saved configs. Hyprpaper's old and current syntax, local config includes, variables, file URIs, KDE wallpaper packages, GNOME slideshow definitions, and XDG config/state/Pictures locations are supported.

Without a usable configured image, it checks standard user wallpaper folders, then `/usr/share/backgrounds`, `/usr/local/share/backgrounds`, `/usr/share/wallpapers`, `/usr/share/hyprland`, and `/usr/share/xfce4/backdrops`. Folder results are explicitly marked as fallbacks; they are not claimed to be the current wallpaper. If nothing is found, Picture shows `not found` and Custom still works. The bundled example is available by its explicit path.

Queries have short timeouts. Config files and `.fehbg` are parsed as data, never sourced or executed. Only existing local image files are selected. The first usable monitor image is used when monitors have different wallpapers. Detection runs when setup/build is invoked; changing a desktop wallpaper later still requires rebuilding and reinstalling the snapshot.

Format references: [Hyprpaper](https://wiki.hypr.land/hypr-ecosystem/user/hyprpaper/), [Waypaper](https://anufrievroman.gitbook.io/waypaper/configuration), [swww query changes](https://github.com/LGFae/swww/blob/main/CHANGELOG.md), [Sway output configuration](https://github.com/swaywm/sway/blob/master/sway/sway-output.5.scd).

## Short and Full sequences

Short remains the default and uses the existing light-up animation. Full adds the actual local `long.mp4` closing footage before that same animation. The source file is unchanged and ignored by Git. Full stops if it is missing or differs from the clip used to calibrate the opening mattes; it does not substitute an invented closing animation.

The marked view area, including the small cable-loop opening, is replaced with `--opening-color` or `--opening-picture`. The cockpit, hands, camera, and moving shutters are decoded from the actual video. Per-frame grayscale mattes under `theme/full/` follow the marked opening and preserve the real shutter pixels. This calibration is specific to the provided clip. Runtime builds need no NumPy or computer-vision package.

Full precomputes PNG playback frames for Plymouth, which cannot directly play the MP4 in this script theme. This increases generated theme/initramfs size. Playback is quantized to the theme's 24 fps and respects the selected speed. The complete source time range is used; the final closed frame is followed by the normal short sequence. The opening picture is a separate choice from the final SDDM/wallpaper panel picture. Video frames use aspect-preserving cover scaling at other screen ratios.

```bash
python3 scripts/build.py --sequence full --sddm-preview --opening-color '#234567' --audio
bash scripts/preview-plymouth.sh --headless full-black
python3 scripts/check-full-preview.py --variant full-black
python3 scripts/check-previews.py --variant full-black
```

Full names are `titanfall-full-black`, `titanfall-full-white`, and `titanfall-full-custom`; preview files use `preview-full-<palette>.mp4`. Original short names remain unchanged. Builds write per-profile `manifest-short.json` and `manifest-full.json`, plus `manifest.json` for the latest build. Native previews select the matching profile manifest, so Short and Full can coexist.

For Full, `--audio` includes the closing clip's own sound. If all three optional local light-up audio files are available, their mix is appended at the light-up handoff as well. Boot audio remains unimplemented.

## Native tests

The preview runs in private user, mount, network, and PID namespaces. It does not select a system theme or modify the host daemon configuration. Headless previews require Xvfb and ImageMagick. Visible previews require X11 or XWayland.

```bash
python3 scripts/test-full-sequence.py
python3 scripts/test-images.py
python3 scripts/test-wallpaper.py
python3 scripts/test-setup.py
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

For a custom build, preview `custom` and use `python3 scripts/check-previews.py --variant custom`. The preview chooses a duration from the matching profile manifest when seconds are omitted. Use a longer explicit duration if needed for a slow animation. Headless captures copy Xvfb's framebuffer immediately and convert it after playback, avoiding screenshot delays during fast panel phases.

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

Short builds do not require the original video or logo. The reference duration is recorded in the layout configuration. If a local `closing-pilot.mp4` exists, its actual metadata and hash are recorded instead; it is never cut or overwritten. The logo is unused.

Short's `--audio` requires local `machine-noise.m4a`, `marauder-corps.m4a`, and `the-line.m4a`. It generates `build/preview-<variant>-audio.mp4`; plain MP4s are silent. Full can use its closing clip's sound without those optional files. No boot-audio service is installed. Original media paths are ignored by Git and excluded from published history.

On the development machine, originals are saved in a local stash named `local original media and logo`. Find its index with `git stash list` and restore with `git stash apply 'stash@{N}'`. Applying preserves the stash backup. Stashes and the `local-original-history` backup branch are not pushed.

## Installation and rollback

The interactive installer supports systems using `plymouth-set-default-theme -R`. Ensure the system already has the appropriate Plymouth initramfs hook and boot arguments, and verify regeneration succeeds before rebooting. The project does not change SDDM or desktop settings or delay boot to finish the animation.

Restore an interactive installation:

```bash
./install.sh --restore
```

For manual installation after previewing (replace `custom` with `black` or `white` if appropriate):

```bash
plymouth-set-default-theme > build/previous-theme.txt
sudo cp -r build/themes/titanfall-custom /usr/share/plymouth/themes/
sudo plymouth-set-default-theme -R titanfall-custom
```

For a manual install, restore with `sudo plymouth-set-default-theme -R "$(cat build/previous-theme.txt)"`.

Changes are saved in separate title-only conventional commits. Inspect a checkpoint without discarding current work:

```bash
git log --oneline
git switch -c inspect-checkpoint COMMIT_HASH
```

References: [Plymouth scripting](https://wiki.freedesktop.org/www/Software/Plymouth/Scripts/), [Plymouth overview](https://wiki.freedesktop.org/www/Software/Plymouth/).
