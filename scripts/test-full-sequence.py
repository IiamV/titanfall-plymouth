#!/usr/bin/env python3
"""Check clip selection and compositing without requiring private source media."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import full_sequence as closing


def pixels(path,format='rgb24'):
    return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-pix_fmt',format,'-f','rawvideo','pipe:1'])


class ClosingSequenceTest(unittest.TestCase):
    def test_legacy_full_alias_selects_long(self):
        self.assertEqual(closing.normalize('full'),'long')
        for sequence in ('short','semi-long','long'):
            self.assertEqual(closing.normalize(sequence),sequence)

    def test_interpolation_preserves_endpoints(self):
        keys=[[0,[[0,0],[10,20]]],[2,[[4,8],[20,40]]]]
        self.assertEqual(closing.interpolate(keys,-1),keys[0][1])
        self.assertEqual(closing.interpolate(keys,1),[[2,4],[15,30]])
        self.assertEqual(closing.interpolate(keys,3),keys[-1][1])

    def test_each_profile_rejects_missing_or_changed_source_before_decoding(self):
        for sequence,filename in closing.PROFILES.items():
            with self.subTest(sequence=sequence),tempfile.TemporaryDirectory() as temp,patch.object(closing,'ROOT',Path(temp)),patch.object(closing,'run') as run:
                with self.assertRaisesRegex(ValueError,filename):closing.prepare(Path(temp)/'build',sequence)
                (Path(temp)/filename).write_bytes(b'different video')
                with self.assertRaisesRegex(ValueError,'differs'):closing.prepare(Path(temp)/'build',sequence)
                run.assert_not_called()

    def test_profile_metadata_covers_entire_clip_and_shared_closing(self):
        profiles={name:json.loads((closing.DATA/name/'tracking.json').read_text()) for name in closing.PROFILES}
        for name,tracking in profiles.items():
            self.assertEqual(tracking['source'],closing.PROFILES[name])
            self.assertEqual(len(tracking['source_sha256']),64)
            times=[entry['time'] for entry in tracking['frames']]
            self.assertEqual(times,sorted(set(times)))
            self.assertGreater(tracking['duration']-times[-1],0)
            self.assertLess(tracking['duration']-times[-1],0.04)
            for entry in tracking['frames']:
                self.assertTrue((closing.DATA/'masks'/f'{entry["mask"]}.png').is_file())
        self.assertEqual(len(profiles['long']['frames']),158)
        self.assertEqual(len(profiles['semi-long']['frames']),45)
        self.assertEqual(profiles['semi-long']['frames'][0]['mask'],profiles['long']['frames'][114]['mask'])
        self.assertNotEqual(profiles['long']['source_sha256'],profiles['semi-long']['source_sha256'])

    @unittest.skipUnless(shutil.which('magick') and shutil.which('ffmpeg'),'ImageMagick and FFmpeg required')
    def test_solid_and_picture_replace_only_mask_and_preserve_actual_footage(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';source.mkdir();mattes=root/'mattes';mattes.mkdir()
            subprocess.run(['magick','-size','960x540','gradient:#152a40-#528caa','PNG24:'+str(source/'0.png')],check=True)
            subprocess.run(['magick','-size','960x540','xc:black','-fill','white','-draw','rectangle 300,100 700,400',str(mattes/'5.png')],check=True)
            picture=root/'picture.png'
            subprocess.run(['magick','-size','960x540','gradient:#b07851-#203052','PNG24:'+str(picture)],check=True)
            tracking={'duration':0.01,'frames':[{'time':0,'mask':5}],'checkpoints':{'moving':0}}
            prepared={'frames':source,'mattes':mattes,'tracking':tracking,'occlusion':{'fade':[[0,1]]},'source':root/'long-new.mp4','sha256':'fixture'}
            original=pixels(source/'0.png')
            for label,image in [('solid',None),('picture',picture)]:
                target=root/label;target.mkdir()
                intro=closing.compose(target,prepared,1.25,24,'#234567',image)
                self.assertEqual(intro['frames'],1)
                self.assertEqual(intro['checkpoints']['moving'],0)
                actual=pixels(target/'intro-0.png');opening=pixels(target/'opening.png');alpha=pixels(target/'intro-mask-0.png','gray')
                for index in range(0,960*540,101):
                    i=index*3
                    if alpha[index]==0:self.assertEqual(actual[i:i+3],original[i:i+3])
                    if alpha[index]==255:self.assertEqual(actual[i:i+3],opening[i:i+3])

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
    def test_masks_follow_camera_and_protect_typing_hand_and_shutters(self):
        def mask(index):return pixels(closing.DATA/'masks'/f'{index}.png','gray')
        initial=mask(0);typing=mask(88);closed=mask(136)
        self.assertGreater(initial[300*960+100],250)  # initial outside fills side
        self.assertEqual(typing[300*960+100],0)  # cockpit has moved into same point
        self.assertEqual(typing[400*960+300],0)  # typing hand remains original
        self.assertGreater(typing[130*960+550],250)  # current opening
        self.assertEqual(closed[170*960+480],0)  # descending canopy
        self.assertEqual(closed[400*960+480],0)  # rising lower shutter
        self.assertGreater(closed[270*960+480],250)  # view between shutters
        self.assertFalse(any(mask(157)))


if __name__=='__main__':unittest.main()
