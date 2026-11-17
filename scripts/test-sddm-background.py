#!/usr/bin/env python3
"""Exercise installed-theme discovery, config precedence, and explicit failures."""
from pathlib import Path
import tempfile
import unittest
from sddm_background import find_sddm_image, SDDMImageNotFound


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.write("etc/sddm.conf.d/theme.conf", "[Theme]\nCurrent=Pilot\n")
        self.theme = "usr/share/sddm/themes/Pilot/"
        self.write(self.theme + "theme.conf", "[General]\nbackground=default.png\n")
        self.write(self.theme + "default.png", "test image")

    def write(self, path, value):
        path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
        return path

    def test_background_and_user_override(self):
        chosen = self.write(self.theme + "custom.png", "user image")
        self.write(self.theme + "theme.conf.user", "[General]\nbackground=custom.png\n")
        self.assertEqual(find_sddm_image(root=self.root).path, chosen)

    def test_etc_main_config_has_final_precedence(self):
        self.write("etc/sddm.conf", "[Theme]\nCurrent=Missing\n")
        with self.assertRaisesRegex(SDDMImageNotFound, "Missing"):
            find_sddm_image(root=self.root)

    def test_metadata_config_and_relative_background(self):
        self.write(self.theme + "metadata.desktop", "[SddmGreeterTheme]\nConfigFile=Themes/custom.conf\n")
        self.write(self.theme + "Themes/custom.conf", "[General]\nBackground=../photo.jpg\n")
        chosen = self.write(self.theme + "photo.jpg", "theme photo")
        self.assertEqual(find_sddm_image(root=self.root).path, chosen)

    def test_packaged_screenshot(self):
        self.write(self.theme + "metadata.desktop", "[SddmGreeterTheme]\nScreenshot=Preview/pilot.png\n")
        chosen = self.write(self.theme + "Preview/pilot.png", "theme screenshot")
        self.assertEqual(find_sddm_image(preview=True, root=self.root).path, chosen)

    def test_missing_background_informs_user(self):
        self.write(self.theme + "theme.conf.user", "[General]\nbackground=missing.png\n")
        with self.assertRaisesRegex(SDDMImageNotFound, "No local background image.*missing.png"):
            find_sddm_image(root=self.root)


if __name__ == "__main__":
    unittest.main()
