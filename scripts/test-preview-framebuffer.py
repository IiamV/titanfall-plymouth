#!/usr/bin/env python3
"""Check headless handoff detection against XWD pixel layouts."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('anchor',Path(__file__).with_name('anchor-preview.py'))
anchor=importlib.util.module_from_spec(spec);spec.loader.exec_module(anchor)


class FramebufferTest(unittest.TestCase):
    def image(self,order,bits,changed=False):
        width,height=3,2;stride=12
        header=[100,7,2,24,width,height,0,order,32,0,32,bits,stride,4,0xff0000,0xff00,0xff,8,256,0,width,height,0,0,0]
        byteorder='little' if order==0 else 'big'
        row=(0x123456).to_bytes(bits//8,byteorder)*width+bytes(stride-width*(bits//8))
        data=bytearray(row*height)
        if changed:data[-stride]^=1
        return struct.pack('>25I',*header)+data

    def test_recognizes_uniform_color_in_supported_pixel_layouts(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'frame.xwd'
            for order in (0,1):
                for bits in (24,32):
                    with self.subTest(order=order,bits=bits):
                        p.write_bytes(self.image(order,bits))
                        uniform,raw=anchor.framebuffer(p,(0x12,0x34,0x56))
                        self.assertTrue(uniform)
                        self.assertEqual(raw,p.read_bytes())
                        self.assertFalse(anchor.framebuffer(p,(0,0,0))[0])

    def test_detects_first_line_pixel(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'frame.xwd';p.write_bytes(self.image(0,32,changed=True))
            self.assertFalse(anchor.framebuffer(p,(0x12,0x34,0x56))[0])


if __name__=='__main__':unittest.main()
