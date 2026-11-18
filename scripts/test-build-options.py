#!/usr/bin/env python3
"""Check user-input validation and speed scaling without generating assets."""
import argparse
import json
import unittest
import shutil
import subprocess
from build import LIGHTING, animation_speed, audio_tempo, hex_color, scaled_config


class BuildOptionsTest(unittest.TestCase):
    def test_hex_normalization(self):
        self.assertEqual(hex_color('#AbC'),'#aabbcc')
        self.assertEqual(hex_color('12ABef'),'#12abef')

    def test_reject_invalid_colors(self):
        for value in ('red','#abcd','#12345678','12345g','<svg>',''):
            with self.subTest(value=value),self.assertRaises(argparse.ArgumentTypeError):
                hex_color(value)

    def test_speed_validation(self):
        for value in ('0.25','1','1.25','4',' 1.25 ','1e0'):
            self.assertEqual(animation_speed(value),float(value))
        for value in ('0','-1','4.1','0.24999','4.0001','nan','NaN','inf','-inf','1e309','-1e309','fast','','1,25','1.25x',None):
            with self.subTest(value=value),self.assertRaises(argparse.ArgumentTypeError):
                animation_speed(value)

    @unittest.skipUnless(shutil.which("ffmpeg"),"FFmpeg is not installed")
    def test_audio_speed_matches_animation(self):
        for speed in (0.25,1,1.25,4):
            data=subprocess.check_output(['ffmpeg','-v','error','-f','lavfi','-i',
                'sine=frequency=440:duration=4:sample_rate=8000','-af',audio_tempo(speed),
                '-f','f32le','pipe:1'])
            self.assertAlmostEqual(len(data)/4/8000,4/speed,delta=0.2)

    def test_speed_preserves_order_and_synchronization(self):
        original=json.loads(LIGHTING.read_text())
        for speed in (0.25,1,1.25,4):
            config=scaled_config(speed)
            self.assertEqual(sorted(config['panels'],key=lambda n:config['panels'][n]['keys'][-2][0]),
                             ['left','middle','right','top','bottom'])
            self.assertEqual(config['panels']['middle']['motion'],[0,0])
            for name,panel in config['panels'].items():
                self.assertAlmostEqual(panel['keys'][-1][0]*speed,original['panels'][name]['keys'][-1][0])
            self.assertAlmostEqual(config['lines']['entrance_duration']*speed,original['lines']['entrance_duration'])
            self.assertAlmostEqual(config['lines']['exit_duration']*speed,original['lines']['exit_duration'])
            self.assertGreaterEqual(min(p['keys'][-2][0] for p in config['panels'].values()),
                                    config['lines']['entrance_start']+config['lines']['entrance_duration'])
        self.assertEqual(json.loads(LIGHTING.read_text()),original)


if __name__=='__main__': unittest.main()
