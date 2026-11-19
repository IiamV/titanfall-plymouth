#!/usr/bin/env python3
"""Verify full-clip matting with synthetic frames and no private media."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import full_sequence as full


def pixels(path,format='rgb24'):
    return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-pix_fmt',format,'-f','rawvideo','pipe:1'])


class FullSequenceTest(unittest.TestCase):
    def test_nested_tracking_interpolation_preserves_endpoints(self):
        keys=[[0,[[0,0],[10,20]]],[2,[[4,8],[20,40]]]]
        self.assertEqual(full.interpolate(keys,-1),keys[0][1])
        self.assertEqual(full.interpolate(keys,1),[[2,4],[15,30]])
        self.assertEqual(full.interpolate(keys,3),keys[-1][1])

    def test_reference_missing_or_changed_is_rejected_before_decoding(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(full,'ROOT',Path(temp)),patch.object(full,'run') as run:
            with self.assertRaisesRegex(ValueError,'local long.mp4'): full.prepare(Path(temp)/'build')
            (Path(temp)/'long.mp4').write_bytes(b'different video')
            with self.assertRaisesRegex(ValueError,'differs'): full.prepare(Path(temp)/'build')
            run.assert_not_called()

    @unittest.skipUnless(shutil.which('magick') and shutil.which('ffmpeg'),'ImageMagick and FFmpeg are required')
    def test_marked_mask_has_main_area_and_cable_hole(self):
        alpha=pixels(full.DATA/'opening-mask.png','gray')
        self.assertGreater(alpha[350*1280+600],250)
        self.assertGreater(alpha[110*1280+690],250)
        self.assertLess(alpha[185*1280+690],5)
        self.assertLess(alpha[300*1280+100],5)

    @unittest.skipUnless(shutil.which('magick') and shutil.which('ffmpeg'),'ImageMagick and FFmpeg are required')
    def test_color_and_picture_replace_only_the_marked_area(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/'source'; source.mkdir()
            subprocess.run(['magick','-size','960x540','gradient:#152a40-#528caa','PNG24:'+str(source/'0.png')],check=True)
            picture=root/'picture.png'
            subprocess.run(['magick','-size','960x540','gradient:#b07851-#203052','PNG24:'+str(picture)],check=True)
            tracking={'duration':0.01,'frames':[{'time':0,'corners':[[0,0],[1280,0],[0,720],[1280,720]]}]}
            prepared={'frames':source,'tracking':tracking,'occlusion':json.loads((full.DATA/'occlusion.json').read_text()),'source':root/'long.mp4','sha256':'fixture'}
            original=pixels(source/'0.png')
            for label,image in [('solid',None),('picture',picture)]:
                target=root/label; target.mkdir()
                intro=full.compose(target,prepared,1.25,24,'#234567',image)
                self.assertEqual(intro['frames'],1)
                actual=pixels(target/'intro-0.png')
                opening=pixels(target/'opening.png')
                alpha=pixels(target/'intro-mask-0.png','gray')
                for index in range(0,960*540,101):
                    i=index*3
                    if alpha[index]==0: self.assertEqual(actual[i:i+3],original[i:i+3])
                    if alpha[index]==255: self.assertEqual(actual[i:i+3],opening[i:i+3])

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg is required')
    def test_real_shutter_areas_remain_original_footage(self):
        mask=pixels(full.DATA/'masks/72.png','gray')
        self.assertEqual(mask[170*960+480],0)  # upper canopy
        self.assertEqual(mask[360*960+480],0)  # rising lower shutter
        self.assertGreater(mask[250*960+480],250)  # view between them

    def test_calibration_is_finite_and_covers_entire_clip(self):
        import math
        tracking=json.loads((full.DATA/'tracking.json').read_text())
        times=[entry['time'] for entry in tracking['frames']]
        self.assertEqual(len(times),89)
        self.assertEqual(times,sorted(set(times)))
        self.assertLess(tracking['duration']-times[-1],0.04)
        for entry in tracking['frames']:
            self.assertEqual(len(entry['corners']),4)
            self.assertTrue(all(math.isfinite(value) and abs(value)<3000 for point in entry['corners'] for value in point))


if __name__=='__main__': unittest.main()
