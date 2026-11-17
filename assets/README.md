# Cockpit closure reference

Source: [Titanfall™ 2 BEST SCENE-Get ready for titanfall!](https://www.youtube.com/watch?v=Sn50EDiLVAk), supplied by the user as the intended visual reference.

`cockpit-close-reference.mp4` is a silent one-second excerpt beginning at 28.6 seconds. The build uses its first 0.8 seconds to extract stable contour samples. The full reference and yt-dlp are kept only in the ignored `.work/` directory.

The important motion is the upper hatch descending while the lower armored plate rises. After the seal, the original footage briefly goes dark and then the cockpit display reopens in segments. This theme recreates the physical closure and replaces that reopening with the requested shared logo/line fade.

The build samples the stationary chassis from the opening pose and moving panel contours from an exposure-stable intermediate pose. It masks the hangar opening, derives transparent monochrome edge images, then moves the upper and lower sprites in opposite vertical directions. The source does not supply precise 3D geometry; the sprite translations are a 2D reconstruction, not an exact reproduction of hinge perspective.

To regenerate the source excerpt if the full reference has been downloaded:

```bash
ffmpeg -ss 28.6 -t 1.0 -i .work/reference.mp4 -an \
  -c:v libx264 -crf 16 -pix_fmt yuv420p assets/cockpit-close-reference.mp4
```
