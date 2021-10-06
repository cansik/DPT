import glob
import os


def get_images_in_path(path: str):
    return get_files_in_path(path, ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.gif', '*.tiff'])


def get_files_in_path(path: str, extensions: [str] = ["*.*"]):
    return sorted([f for ext in extensions for f in glob.glob(os.path.join(path, ext))])