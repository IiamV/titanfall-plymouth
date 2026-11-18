"""Validate user-selected local images before building assets."""
import os
from pathlib import Path
import shutil
import subprocess
import unicodedata
from urllib.parse import unquote,urlparse

EXTENSIONS={'.png','.jpg','.jpeg','.webp','.svg','.svgz','.bmp','.gif','.avif','.heic','.heif','.tif','.tiff','.jxl','.ppm','.pgm','.pbm'}
FORMATS={'PNG','PNG8','PNG24','PNG32','PNG48','PNG64','JPEG','JPG','WEBP','SVG','SVGZ','MSVG','BMP','BMP2','BMP3','GIF','AVIF','HEIC','HEIF','TIFF','JXL','PPM','PGM','PBM','PNM'}


def validate_image(value):
    value=str(value).strip()
    if not value: raise ValueError('Enter an image path, or leave the optional picture prompt blank.')
    if any(unicodedata.category(character)=='Cc' for character in value):
        raise ValueError('The image path contains control characters.')
    if value[0] in ('\"',"'"):
        if len(value)<2 or value[-1]!=value[0]: raise ValueError('The image path has an unmatched quote.')
        value=value[1:-1]
    value=os.path.expandvars(value)
    parsed=urlparse(value)
    if parsed.scheme:
        if parsed.scheme!='file' or parsed.netloc not in ('','localhost'):
            raise ValueError('Choose a local image file; remote URLs are not supported.')
        value=unquote(parsed.path)
    if any(unicodedata.category(character)=='Cc' for character in value):
        raise ValueError('The image path contains control characters.')
    try:
        path=Path(value).expanduser().resolve(strict=True)
        if not path.is_file(): raise ValueError('Choose an image file, not a directory.')
        if path.suffix.lower() not in EXTENSIONS: raise ValueError('Unsupported image extension. Use PNG, JPEG, WebP, SVG, or another supported image format.')
        with path.open('rb') as stream:
            if not stream.read(1): raise ValueError('The image file is empty.')
    except (OSError,RuntimeError) as error:
        raise ValueError(f'Image is missing or unreadable: {value}') from error
    if not shutil.which('magick'): raise ValueError('Image validation requires ImageMagick (magick).')
    try:
        # Decode frame zero, rather than trusting an extension or file header.
        probe=subprocess.run(['magick',str(path)+'[0]','-format','%m %w %h','info:'],
                             capture_output=True,text=True,errors='replace',timeout=5,check=True)
        format_name,width,height=probe.stdout.strip().split()
        if format_name.upper() not in FORMATS or int(width)<=0 or int(height)<=0:
            raise ValueError('Unsupported image format or invalid image dimensions.')
    except subprocess.TimeoutExpired as error:
        raise ValueError('The image took too long to decode. Choose a smaller or simpler image.') from error
    except (OSError,subprocess.CalledProcessError) as error:
        raise ValueError('The file cannot be decoded as an image; it may be corrupt or unsupported.') from error
    except (ValueError,TypeError) as error:
        raise ValueError('The image has an unsupported format or invalid dimensions.') from error
    return path
