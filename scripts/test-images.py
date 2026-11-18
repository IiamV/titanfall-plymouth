#!/usr/bin/env python3
"""Check custom image path handling and actual decoder validation."""
from pathlib import Path
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zlib
from images import validate_image


def png_bytes():
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+
            chunk(b'IDAT',zlib.compress(b'\x00\x80\x90\xa0'))+chunk(b'IEND',b''))


@unittest.skipUnless(shutil.which('magick'),'ImageMagick is required')
class ImageTest(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.picture=self.root/'pilot image.png'
        self.picture.write_bytes(png_bytes())

    def test_valid_image_spaces_quotes_and_uri(self):
        for value in (str(self.picture),f'"{self.picture}"',f"'{self.picture}'",self.picture.as_uri()):
            with self.subTest(value=value): self.assertEqual(validate_image(value),self.picture)

    def test_tilde_environment_variables_and_relative_path(self):
        with patch.dict(os.environ,{'HOME':str(self.root),'PILOT_IMAGE':str(self.picture)}):
            self.assertEqual(validate_image('~/pilot image.png'),self.picture)
            self.assertEqual(validate_image('$PILOT_IMAGE'),self.picture)
        with patch.dict(os.environ,{'PILOT_IMAGE_URI':self.picture.as_uri()}):
            self.assertEqual(validate_image('$PILOT_IMAGE_URI'),self.picture)
        previous=Path.cwd()
        try:
            os.chdir(self.root)
            self.assertEqual(validate_image('pilot image.png'),self.picture)
        finally: os.chdir(previous)

    def test_missing_directory_empty_corrupt_and_wrong_extension(self):
        empty=self.root/'empty.png'; empty.touch()
        corrupt=self.root/'corrupt.png'; corrupt.write_text('not an image')
        wrong=self.root/'script.sh'; wrong.write_text('echo should-not-run')
        for value in (self.root/'missing.png',self.root,empty,corrupt,wrong):
            with self.subTest(value=value),self.assertRaises(ValueError): validate_image(value)

    def test_symlinks_and_uppercase_extension(self):
        alias=self.root/'LINK.PNG'; alias.symlink_to(self.picture)
        self.assertEqual(validate_image(alias),self.picture)
        broken=self.root/'broken.png'; broken.symlink_to(self.root/'missing.png')
        with self.assertRaises(ValueError): validate_image(broken)

    def test_remote_urls_controls_and_unmatched_quotes(self):
        for value in ('https://example.com/image.png','file://remote/image.png','file:///tmp/test%00.png','file:///tmp/test%0A.png','\x00.png','\x1b.png','\u0085.png',f'"{self.picture}',''):
            with self.subTest(value=value),self.assertRaises(ValueError): validate_image(value)

    def test_metacharacters_remain_a_literal_filename(self):
        picture=self.root/'image $(touch marker);.png'
        picture.write_bytes(png_bytes())
        self.assertEqual(validate_image(picture),picture)
        self.assertFalse((self.root/'marker').exists())

    def test_permission_failure_has_clear_validation_error(self):
        with patch('images.Path.open',side_effect=PermissionError('denied')):
            with self.assertRaisesRegex(ValueError,'unreadable'): validate_image(self.picture)

    def test_missing_decoder_and_decode_timeout(self):
        with patch('images.shutil.which',return_value=None):
            with self.assertRaisesRegex(ValueError,'ImageMagick'): validate_image(self.picture)
        with patch('images.subprocess.run',side_effect=subprocess.TimeoutExpired(['magick'],5)):
            with self.assertRaisesRegex(ValueError,'too long'): validate_image(self.picture)

    def test_unexpected_decoder_output_is_rejected(self):
        for output in ('PNG 0 1','PNG -1 10','PNG many 10','PDF 1 1','not image dimensions'):
            with self.subTest(output=output),patch('images.subprocess.run',return_value=subprocess.CompletedProcess([],0,output,'')):
                with self.assertRaises(ValueError): validate_image(self.picture)


if __name__=='__main__': unittest.main()
