# Titanfall Plymouth

Cockpit panels light up **left → middle → right → top → bottom**, revealing your SDDM picture or wallpaper. Fixed internal seams draw inward, then retract outward. No outer border or logo.

## Demos

| Black | White |
| --- | --- |
| ![Black SDDM demo](docs/demo/black.gif) | ![White SDDM demo](docs/demo/white.gif) |

[Black with sound](docs/demo/black-audio.mp4) · [White with sound](docs/demo/white-audio.mp4)

**Wallpaper with cyan lines and 1.25× speed**

![Wallpaper panel animation](docs/demo/wallpaper.gif)

[Wallpaper video](docs/demo/wallpaper.mp4) · [Example wallpaper](docs/demo/wallpaper.svg)

## Build and try

Needs **Python 3, FFmpeg, ImageMagick, and Plymouth's script plugin**. Builds work without the original reference media.

```bash
python3 scripts/build.py --sddm-preview
ffplay -autoexit build/preview-black.mp4
```

This discovers your SDDM theme's packaged screenshot. Use `--sddm-background` for its configured background instead. A missing image produces an error.

Customize a wallpaper, colors, and speed:

```bash
python3 scripts/build.py --background docs/demo/wallpaper.svg \
  --panel-color '#0b1220' --line-color '#6ee7ff' --speed 1.25
ffplay -autoexit build/preview-custom.mp4
```

- `--panel-color`: backdrop and solid-panel color; a wallpaper keeps its own colors. Omit `--background` for solid panels.
- `--line-color`: seam color. Accepts quoted `'#RGB'` or `'#RRGGBB'`; omitted lines use automatic black/white contrast.
- `--speed`: `1` is normal, `1.25` is faster, `0.75` is slower. Range: `0.25–4`; affects the whole animation.

Without color options, both black and white variants are built. Color options create `titanfall-custom`. Changing settings requires rebuilding the theme.

Native preview without installing (X11/XWayland):

```bash
bash scripts/preview-plymouth.sh custom
```

## Install after previewing

Replace `custom` with `black` or `white` for a default variant.

```bash
plymouth-set-default-theme > build/previous-theme.txt
sudo cp -r build/themes/titanfall-custom /usr/share/plymouth/themes/
sudo plymouth-set-default-theme -R titanfall-custom
```

The picture is a snapshot, not live SDDM. Audio is optional in video previews; boot audio is not implemented. See [testing, audio, and rollback](docs/DEVELOPMENT.md) for details.
