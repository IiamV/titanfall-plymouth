#!/usr/bin/env python3
"""Exercise interactive options and installation rollback without host writes."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import os
import unicodedata
import unittest
from unittest.mock import patch
import setup
from sddm_background import SDDMImage, SDDMImageNotFound
from wallpaper import Wallpaper, WallpaperNotFound


class SetupTest(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.themes=self.root/'system-themes'
        self.themes.mkdir()
        self.root_patch=patch.object(setup,'ROOT',self.root)
        self.theme_patch=patch.object(setup,'THEMES',self.themes)
        self.root_patch.start(); self.theme_patch.start()
        self.addCleanup(self.root_patch.stop); self.addCleanup(self.theme_patch.stop)
        self.sddm=self.root/'sddm-preview.png'
        self.sddm.write_bytes(b'image')
        picture=self.root/'docs/demo/wallpaper.svg'
        picture.parent.mkdir(parents=True)
        picture.write_text('<svg/>')
        discovery=patch.object(setup,'find_sddm_image',return_value=SDDMImage(self.sddm,'test','packaged theme screenshot'))
        discovery.start(); self.addCleanup(discovery.stop)
        wallpaper=patch.object(setup,'find_wallpaper',return_value=Wallpaper(picture,'test desktop','configured'))
        wallpaper.start(); self.addCleanup(wallpaper.stop)
        self.output=contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__(); self.addCleanup(self.output.__exit__,None,None,None)

    def generated(self):
        source=self.root/'build/themes/titanfall-custom'
        source.mkdir(parents=True)
        (source/'titanfall-custom.plymouth').write_text('descriptor')
        (source/'titanfall-custom.script').write_text('new script')
        return source

    def fake_privileged(self,command):
        if command[0]=='install': Path(command[-1]).mkdir(parents=True,exist_ok=True)
        if command[0]=='cp': shutil.copytree(Path(command[-2]),Path(command[-1]),dirs_exist_ok=True)

    def test_long_paths_wrap_without_truncating_or_autowrapping(self):
        options=['SDDM — /usr/share/sddm/themes/WarGames/preview.png',
                 'Picture — /home/someone/a long project path/docs/demo/wallpaper.svg',
                 'Custom — enter an image path']
        for columns in (24,40,80,120):
            rows=setup.menu_lines(options,1,columns)
            for row in rows:
                width=sum(0 if unicodedata.combining(c) else (2 if unicodedata.east_asian_width(c) in ('W','F') else 1) for c in row)
                self.assertLessEqual(width,columns-1)
            text=''.join(rows)
            for option in options: self.assertIn(option,text)

    def test_redraw_moves_up_by_wrapped_rows(self):
        class Terminal(io.StringIO):
            def isatty(self): return True
            def fileno(self): return 99
        incoming,outgoing=Terminal(),Terminal()
        options=['SDDM — /a/very/long/path/to/the/installed/theme/preview.png',
                 'Picture — /another/very/long/path/to/wallpaper.svg','Custom']
        expected=len(setup.menu_lines(options,0,30))-1
        with patch.object(setup.sys,'stdin',incoming),patch.object(setup.sys,'stdout',outgoing),patch.dict(setup.os.environ,{'TERM':'xterm'}),patch.object(setup.os,'get_terminal_size',return_value=os.terminal_size((30,24))),patch.object(setup.termios,'tcgetattr',return_value=[]),patch.object(setup.termios,'tcsetattr'),patch.object(setup.tty,'setcbreak'),patch.object(setup.os,'read',side_effect=[b'j',b'k',b'\n']):
            self.assertEqual(setup.choose('Picture',options),0)
        self.assertGreater(expected,len(options))
        self.assertEqual(outgoing.getvalue().count(f'\033[{expected}A'),2)

    def test_numbered_menu_retries_invalid_choices(self):
        with patch.object(setup.sys,'stdin',io.StringIO()),patch('builtins.input',side_effect=['0','bad','2']):
            self.assertEqual(setup.choose('Test',['first','second']),1)

    def test_failed_restore_keeps_rollback_history(self):
        self.generated()
        existing=self.themes/'titanfall-custom'
        existing.mkdir()
        (existing/'titanfall-custom.script').write_text('old script')
        def fail_rebuild(command):
            self.fake_privileged(command)
            if command[0]=='plymouth-set-default-theme':
                raise subprocess.CalledProcessError(1,command)
        with patch.object(setup.shutil,'which',return_value='/usr/bin/tool'),patch.object(setup.subprocess,'check_output',return_value='old-theme\n'),patch.object(setup,'run_privileged',side_effect=fail_rebuild):
            with self.assertRaises(subprocess.CalledProcessError): setup.install_theme('custom')
        self.assertEqual(setup.read_history()[-1]['previous'],'old-theme')
        self.assertTrue((self.root/setup.read_history()[-1]['backup']).is_dir())

    def test_optional_solid_custom_colors_and_speed(self):
        with patch.object(setup,'choose',side_effect=[2,2]),patch('builtins.input',side_effect=['','#abc','auto','1.25']):
            options=setup.collect_options()
        self.assertIsNone(options['picture'])
        self.assertEqual(options['panel_color'],'#aabbcc')
        self.assertEqual(options['speed'],1.25)
        self.assertNotIn('--background',options['command'])
        self.assertNotIn('--line-color',options['command'])
        self.assertEqual(options['variant'],'custom')

    def test_menu_shows_exact_sddm_and_picture_paths(self):
        with patch.object(setup,'choose',side_effect=[1,0]) as menu,patch('builtins.input',return_value='1'):
            options=setup.collect_options()
        labels=menu.call_args_list[0].args[1]
        picture=str(self.root/'docs/demo/wallpaper.svg')
        self.assertEqual(labels,[f'SDDM — {self.sddm}',f'Picture — {picture}','Custom — enter an image path'])
        self.assertEqual(options['picture'],picture)
        self.assertEqual(options['command'][options['command'].index('--background')+1],picture)

    def test_missing_wallpaper_allows_custom_fallback(self):
        with patch.object(setup,'find_wallpaper',side_effect=WallpaperNotFound('missing wallpaper')),patch.object(setup,'choose',side_effect=[1,2,0]) as menu,patch('builtins.input',side_effect=['','1']):
            options=setup.collect_options()
        self.assertEqual(menu.call_args_list[0].args[1][1],'Picture — not found')
        self.assertIsNone(options['picture'])

    def test_default_folder_is_marked_as_fallback(self):
        picture=self.root/'docs/demo/wallpaper.svg'
        with patch.object(setup,'find_wallpaper',return_value=Wallpaper(picture,'default wallpaper folder','fallback')),patch.object(setup,'choose',side_effect=[1,0]) as menu,patch('builtins.input',return_value='1'):
            options=setup.collect_options()
        self.assertIn('— default-folder fallback',menu.call_args_list[0].args[1][1])
        self.assertEqual(options['picture'],str(picture))

    def test_sddm_build_uses_the_displayed_image(self):
        with patch.object(setup,'choose',side_effect=[0,0]),patch('builtins.input',return_value='1'):
            options=setup.collect_options()
        self.assertEqual(options['picture'],str(self.sddm))
        self.assertEqual(options['command'][options['command'].index('--background')+1],str(self.sddm))

    def test_wallpaper_path_is_one_argument(self):
        wallpaper=self.root/'my wallpaper $(no shell).png'
        wallpaper.write_bytes(b'example')
        with patch.object(setup,'choose',side_effect=[2,0]),patch('builtins.input',side_effect=[str(wallpaper),'1']):
            options=setup.collect_options()
        self.assertEqual(options['command'][options['command'].index('--background')+1],str(wallpaper))
        self.assertEqual(options['variant'],'black')

    def test_missing_sddm_allows_solid_fallback(self):
        with patch.object(setup,'choose',side_effect=[0,2,1]),patch.object(setup,'find_sddm_image',side_effect=SDDMImageNotFound('missing image')),patch('builtins.input',side_effect=['','1']):
            options=setup.collect_options()
        self.assertIsNone(options['picture'])
        self.assertEqual(options['variant'],'white')

    def test_preview_only_never_offers_install(self):
        options={'variant':'custom','picture':None,'panel_color':'#123456','line_color':'auto','speed':1,'command':['python3','build.py']}
        with patch('sys.argv',['setup.py','--preview-only']),patch.object(setup,'check_dependencies'),patch.object(setup,'collect_options',return_value=options),patch.object(setup,'build_theme',return_value=self.root/'preview.mp4'),patch.object(setup,'confirm',return_value=False) as confirm,patch.object(setup,'install_theme') as install:
            setup.main()
        confirm.assert_called_once_with('Open the video preview now?')
        install.assert_not_called()

    def test_install_and_restore_preserve_same_theme_assets(self):
        self.generated()
        existing=self.themes/'titanfall-custom'
        existing.mkdir()
        (existing/'titanfall-custom.script').write_text('old script')
        with patch.object(setup.shutil,'which',return_value='/usr/bin/tool'),patch.object(setup.subprocess,'check_output',return_value='titanfall-custom\n'),patch.object(setup,'run_privileged',side_effect=self.fake_privileged) as privileged:
            setup.install_theme('custom')
            self.assertEqual((existing/'titanfall-custom.script').read_text(),'new script')
            self.assertEqual(len(setup.read_history()),1)
            setup.restore_last()
            self.assertEqual((existing/'titanfall-custom.script').read_text(),'old script')
        self.assertEqual(setup.read_history(),[])
        self.assertIn(unittest.mock.call(['plymouth-set-default-theme','-R','titanfall-custom']),privileged.call_args_list)

    def test_failed_rebuild_restores_previous_assets_and_theme(self):
        self.generated()
        existing=self.themes/'titanfall-custom'
        existing.mkdir()
        (existing/'titanfall-custom.script').write_text('old script')
        failed=False
        def fail_once(command):
            nonlocal failed
            self.fake_privileged(command)
            if command[0]=='plymouth-set-default-theme' and not failed:
                failed=True
                raise subprocess.CalledProcessError(1,command)
        with patch.object(setup.shutil,'which',return_value='/usr/bin/tool'),patch.object(setup.subprocess,'check_output',return_value='old-theme\n'),patch.object(setup,'run_privileged',side_effect=fail_once) as privileged:
            with self.assertRaises(subprocess.CalledProcessError): setup.install_theme('custom')
        self.assertEqual((existing/'titanfall-custom.script').read_text(),'old script')
        self.assertEqual(setup.read_history(),[])
        privileged.assert_called_with(['plymouth-set-default-theme','-R','old-theme'])

    def test_invalid_restore_paths_cannot_run_privileged_commands(self):
        entry={'theme':'titanfall-custom','previous':'../../etc/passwd','backup':None}
        with patch.object(setup,'run_privileged') as privileged:
            with self.assertRaises(RuntimeError): setup.restore_entry(entry)
            entry['previous']='valid'
            entry['backup']='/etc'
            with self.assertRaises(RuntimeError): setup.restore_entry(entry)
        privileged.assert_not_called()

    def test_declining_install_leaves_system_unchanged(self):
        options={'variant':'custom','picture':None,'panel_color':'#123456','line_color':'auto','speed':1,'command':['python3','build.py']}
        with patch('sys.argv',['setup.py']),patch.object(setup,'check_dependencies'),patch.object(setup,'collect_options',return_value=options),patch.object(setup,'build_theme',return_value=self.root/'preview.mp4'),patch.object(setup,'confirm',return_value=False),patch.object(setup,'install_theme') as install:
            setup.main()
        install.assert_not_called()


if __name__=='__main__': unittest.main()
