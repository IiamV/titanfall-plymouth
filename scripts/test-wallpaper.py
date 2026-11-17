#!/usr/bin/env python3
"""Validate wallpaper discovery against isolated desktop/WM fixtures."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from wallpaper import WallpaperNotFound,find_wallpaper,query


class WallpaperTest(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name)
        self.home=self.base/'home/user'
        self.root=self.base/'system'
        self.home.mkdir(parents=True)
        self.root.mkdir()
        self.env={'XDG_CURRENT_DESKTOP':''}
        self.responses={}
        self.calls=[]

    def write(self,path,text='image'):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text)
        return path

    def config(self,name,text): return self.write(self.home/'.config'/name,text)

    def run_query(self,command):
        self.calls.append(tuple(command))
        return self.responses.get(tuple(command),'')

    def find(self): return find_wallpaper(self.home,self.root,self.env,self.run_query)

    def test_swww_active_image_precedes_stale_configs(self):
        current=self.write(self.home/'Pictures/active wallpaper.png')
        stale=self.write(self.home/'Pictures/stale.png')
        self.config('waypaper/config.ini',f'[Settings]\nwallpaper={stale}')
        self.responses[('swww','query')]=f'namespace: DP-1: 1920x1080, scale: 1, currently displaying: image: {current}'
        found=self.find()
        self.assertEqual((found.path,found.kind,found.source),(current,'active','swww'))

    def test_awww_skips_missing_monitor_image(self):
        current=self.write(self.home/'Pictures/second.webp')
        self.responses[('awww','query')]=f'DP-1: currently displaying: image: /missing.png\nDP-2: currently displaying: image: {current}'
        self.assertEqual(self.find().path,current)

    def test_hyprpaper_active_query(self):
        current=self.write(self.home/'Pictures/active.png')
        self.env['XDG_CURRENT_DESKTOP']='Hyprland'
        self.responses[('hyprctl','hyprpaper','listactive')]=f'eDP-1 = {current}'
        self.assertEqual(self.find().kind,'active')
        self.assertEqual(self.find().path,current)

    def test_hyprpaper_block_variables_and_include(self):
        current=self.write(self.home/'Pictures/hypr image.jpg')
        self.env['XDG_CURRENT_DESKTOP']='Hyprland'
        self.config('hypr/hyprpaper.conf','$wall = ~/Pictures/hypr image.jpg\nsource = backgrounds.conf')
        self.config('hypr/backgrounds.conf','wallpaper {\n monitor = DP-1\n path = $wall\n}')
        self.assertEqual(self.find().path,current)
        self.assertEqual(self.find().source,'Hyprpaper')

    def test_hyprpaper_legacy_ignores_preload_only_images(self):
        unused=self.write(self.home/'Pictures/preloaded.jpg')
        current=self.write(self.home/'Pictures/selected.jpg')
        self.config('hypr/hyprpaper.conf',f'preload = {unused}\nwallpaper = DP-1,contain:{current}')
        self.assertEqual(self.find().path,current)

    def test_sway_variables_include_and_spaces(self):
        current=self.write(self.home/'Pictures/sway image.png')
        self.config('sway/config',f'set $bg "{current}"\ninclude conf.d/*.conf')
        self.config('sway/conf.d/outputs.conf','output * bg $bg fill')
        self.assertEqual(self.find().path,current)
        self.assertEqual(self.find().source,'Sway')

    def test_swaybg_image_argument(self):
        current=self.write(self.home/'Pictures/swaybg image.png')
        self.config('sway/config',f'exec swaybg -i "{current}" -m fill')
        self.assertEqual(self.find().path,current)

    def test_gnome_respects_dark_mode_and_file_uris(self):
        dark=self.write(self.home/'Pictures/dark image.png')
        light=self.write(self.home/'Pictures/light.png')
        self.env['XDG_CURRENT_DESKTOP']='ubuntu:GNOME'
        self.responses[('gsettings','get','org.gnome.desktop.interface','color-scheme')]='\'prefer-dark\''
        self.responses[('gsettings','get','org.gnome.desktop.background','picture-uri-dark')]=repr(dark.as_uri())
        self.responses[('gsettings','get','org.gnome.desktop.background','picture-uri')]=repr(light.as_uri())
        self.assertEqual(self.find().path,dark)
        self.assertNotIn(('gsettings','get','org.gnome.desktop.background','picture-uri'),self.calls)

    def test_cinnamon_and_mate(self):
        for desktop,schema,key in [('Cinnamon','org.cinnamon.desktop.background','picture-uri'),('MATE','org.mate.background','picture-filename')]:
            with self.subTest(desktop=desktop):
                current=self.write(self.home/f'Pictures/{desktop}.png')
                self.env['XDG_CURRENT_DESKTOP']=desktop
                self.responses={('gsettings','get',schema,key):repr(str(current))}
                self.assertEqual(self.find().path,current)

    def test_kde_package_selects_largest_wallpaper_not_preview(self):
        self.env['XDG_CURRENT_DESKTOP']='KDE'
        self.write(self.root/'usr/share/wallpapers/Test/contents/screenshot.png')
        self.write(self.root/'usr/share/wallpapers/Test/contents/images/1024x768.png')
        large=self.write(self.root/'usr/share/wallpapers/Test/contents/images/3840x2160.png')
        self.config('plasma-org.kde.plasma.desktop-appletsrc','[Containments][1][Wallpaper][org.kde.image][General]\nImage=file:///usr/share/wallpapers/Test')
        self.assertEqual(self.find().path,large)
        self.assertEqual(self.find().source,'KDE Plasma')

    def test_xfce_saved_xml(self):
        current=self.write(self.home/'Pictures/xfce.png')
        self.config('xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml',f'<channel><property name="last-image" value="{current}"/></channel>')
        self.assertEqual(self.find().path,current)

    def test_waypaper_xdg_state_overrides_config(self):
        old=self.write(self.home/'Pictures/old.png')
        current=self.write(self.home/'Pictures/current.png')
        self.config('waypaper/config.ini',f'[Settings]\nwallpaper={old}\nuse_xdg_state=True')
        self.write(self.home/'.local/state/waypaper/state.ini',f'[Settings]\nwallpaper={current}')
        self.assertEqual(self.find().path,current)

    def test_feh_script_is_parsed_never_executed(self):
        current=self.write(self.home/'Pictures/$(touch marker) image.png')
        marker=self.home/'marker'
        self.write(self.home/'.fehbg',f'#!/bin/sh\ntouch "{marker}"\nfeh --no-fehbg --bg-fill \'{current}\'')
        self.assertEqual(self.find().path,current)
        self.assertFalse(marker.exists())
        self.assertEqual(self.calls,[('swww','query'),('awww','query')])

    def test_nitrogen(self):
        current=self.write(self.home/'Pictures/nitrogen.png')
        self.config('nitrogen/bg-saved.cfg',f'[xin_-1]\nfile={current}\nmode=5')
        self.assertEqual(self.find().path,current)

    def test_pywal(self):
        current=self.write(self.home/'Pictures/wal.png')
        self.write(self.home/'.cache/wal/colors.json',json.dumps({'wallpaper':str(current)}))
        self.assertEqual(self.find().path,current)

    def test_slideshow_xml_resolves_local_image(self):
        current=self.write(self.home/'Pictures/slide.png')
        slides=self.write(self.home/'Pictures/slides.xml',f'<background><static><file><size>{current}</size></file></static></background>')
        self.config('waypaper/config.ini',f'[Settings]\nwallpaper={slides}')
        self.assertEqual(self.find().path,current)

    def test_user_folder_precedes_distro_defaults_and_ignores_videos(self):
        self.write(self.home/'Pictures/Wallpapers/a.mp4')
        current=self.write(self.home/'Pictures/Wallpapers/b.webp')
        self.write(self.root/'usr/share/backgrounds/default.jpg')
        self.assertEqual(self.find().path,current)
        self.assertEqual(self.find().kind,'fallback')

    def test_xdg_picture_directory_and_config_home(self):
        self.env['XDG_CONFIG_HOME']=str(self.home/'custom-config')
        self.write(self.home/'custom-config/user-dirs.dirs','XDG_PICTURES_DIR="$HOME/Images"')
        current=self.write(self.home/'Images/Wallpapers/wall.png')
        self.assertEqual(self.find().path,current)

    def test_default_image_alias_symlink(self):
        current=self.write(self.home/'images/real.png')
        (self.home/'.background-image').symlink_to(current)
        self.assertEqual(self.find().path,current)

    def test_default_system_folder(self):
        current=self.write(self.root/'usr/share/wallpapers/distro/default.png')
        self.assertEqual(self.find().path,current)
        self.assertEqual(self.find().source,'default wallpaper folder')

    def test_missing_and_remote_images_are_not_silently_replaced(self):
        self.config('waypaper/config.ini','[Settings]\nwallpaper=https://example.com/picture.jpg')
        with self.assertRaises(WallpaperNotFound): self.find()

    def test_queries_have_timeout_and_do_not_use_a_shell(self):
        with patch('wallpaper.shutil.which',return_value='/usr/bin/swww'),patch('wallpaper.subprocess.run',side_effect=subprocess.TimeoutExpired(['swww','query'],0.8)) as run:
            self.assertEqual(query(['swww','query']),'')
        self.assertEqual(run.call_args.args[0],['swww','query'])
        self.assertEqual(run.call_args.kwargs['timeout'],0.8)
        self.assertNotIn('shell',run.call_args.kwargs)


if __name__=='__main__': unittest.main()
