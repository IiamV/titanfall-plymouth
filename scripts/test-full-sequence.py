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

    def test_every_source_frame_has_its_own_explicit_overlay(self):
        import math
        data=json.loads((closing.DATA/'rotoscope.json').read_text())
        self.assertEqual([e['frame'] for e in data['frames']],list(range(158)))
        for entry in data['frames']:
            for path in [entry['outline'],*entry['wires'],*entry['occluders']]:
                self.assertTrue(all(math.isfinite(c) for point in path for c in point))
            if entry['frame']<141:
                self.assertGreater(len(entry['outline']),150)
                self.assertEqual(len(entry['wires']),2)
            if entry['frame']>=142:
                self.assertFalse(entry['outline'])
        self.assertEqual(data['output_canvas'],[960,540])

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
    def test_external_arm_upper_view_and_loop_interior_are_replaced(self):
        for frame in (48,56,64,112,120,124):
            mask=pixels(closing.DATA/'masks'/f'{frame}.png','gray')
            with self.subTest(frame=frame):
                # The user marked this external arm as part of the outside.
                self.assertGreater(mask[255*960+630],250)
                # Grey view under the upper bracket is not cockpit material.
                self.assertGreater(mask[81*960+405],250)
                # Preserve thin cables, not the whole grey area inside a U.
                loop_x,loop_y=(532,82) if frame==112 else (525,112)
                self.assertGreater(mask[loop_y*960+loop_x],250)

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
    def test_cables_remain_continuous_in_each_visible_frame(self):
        data=json.loads((closing.DATA/'rotoscope.json').read_text())
        for frame in range(141):
            mask=pixels(closing.DATA/'masks'/f'{frame}.png','gray')
            for path in data['frames'][frame]['wires']:
                for x,y in path[8:-8:4]:
                    px,py=round(x*1.5),round(y*1.5)
                    if not (2<=px<958 and 2<=py<538):continue
                    retained=min(mask[(py+dy)*960+px+dx] for dy in (-1,0,1) for dx in (-1,0,1))
                    self.assertLess(retained,128,f'Wire vanished in frame {frame}')

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
    def test_no_source_islands_in_the_closing_slot(self):
        # Midpoints sampled from the supplied closing footage, rather than
        # accepting whatever boundary the mask generator happens to produce.
        slot_y={124:175,125:173,126:174,127:176,128:177,129:177,
                130:178,131:178,132:179,133:179,134:181,135:183,
                136:185,137:187,138:190,139:194,140:197}
        for frame,y in slot_y.items():
            mask=pixels(closing.DATA/'masks'/f'{frame}.png','gray')
            with self.subTest(frame=frame):
                self.assertGreater(mask[round(y*1.5)*960+480],250)

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
