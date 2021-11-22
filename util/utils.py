import glob
import os
import shlex
import subprocess

from sys import platform
from natsort import natsort


def chunks(l, n):
    n = max(1, n)
    return (l[i:i + n] for i in range(0, len(l), n))


def replace_ext(path, new_extension) -> str:
    return os.path.splitext(path)[0] + new_extension


def get_images_in_path(path: str):
    return get_files_in_path(path, ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.gif', '*.tiff'])


def get_files_in_path(path: str, extensions: [str] = ["*.*"]):
    return natsort([f for ext in extensions for f in glob.glob(os.path.join(path, ext))])


def call(command: str, cwd=None) -> int:
    if cwd is None:
        cwd = os.getcwd()

    if platform == "linux" or platform == "linux2":
        # linux
        return subprocess.call(shlex.split(command), shell=False, cwd=cwd)
    elif platform == "darwin":
        # MAC OS X
        return subprocess.call(shlex.split(command), shell=False, cwd=cwd)
    elif platform == "win32":
        # Windows
        return subprocess.call(shlex.split(command, posix=False), shell=True, cwd=cwd, env=os.environ)
