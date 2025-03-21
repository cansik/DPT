"""Utils for monoDepth.
"""
import math
import sys
import re
import time

import numpy as np
import cv2
import torch

import glob
import os

from PIL import Image

from .pallete import get_mask_pallete


def read_pfm(path):
    """Read pfm file.

    Args:
        path (str): path to file

    Returns:
        tuple: (data, scale)
    """
    with open(path, "rb") as file:

        color = None
        width = None
        height = None
        scale = None
        endian = None

        header = file.readline().rstrip()
        if header.decode("ascii") == "PF":
            color = True
        elif header.decode("ascii") == "Pf":
            color = False
        else:
            raise Exception("Not a PFM file: " + path)

        dim_match = re.match(r"^(\d+)\s(\d+)\s$", file.readline().decode("ascii"))
        if dim_match:
            width, height = list(map(int, dim_match.groups()))
        else:
            raise Exception("Malformed PFM header.")

        scale = float(file.readline().decode("ascii").rstrip())
        if scale < 0:
            # little-endian
            endian = "<"
            scale = -scale
        else:
            # big-endian
            endian = ">"

        data = np.fromfile(file, endian + "f")
        shape = (height, width, 3) if color else (height, width)

        data = np.reshape(data, shape)
        data = np.flipud(data)

        return data, scale


def write_pfm(path, image, scale=1):
    """Write pfm file.

    Args:
        path (str): pathto file
        image (array): data
        scale (int, optional): Scale. Defaults to 1.
    """

    with open(path, "wb") as file:
        color = None

        if image.dtype.name != "float32":
            raise Exception("Image dtype must be float32.")

        image = np.flipud(image)

        if len(image.shape) == 3 and image.shape[2] == 3:  # color image
            color = True
        elif (
                len(image.shape) == 2 or len(image.shape) == 3 and image.shape[2] == 1
        ):  # greyscale
            color = False
        else:
            raise Exception("Image must have H x W x 3, H x W x 1 or H x W dimensions.")

        file.write("PF\n" if color else "Pf\n".encode())
        file.write("%d %d\n".encode() % (image.shape[1], image.shape[0]))

        endian = image.dtype.byteorder

        if endian == "<" or endian == "=" and sys.byteorder == "little":
            scale = -scale

        file.write("%f\n".encode() % scale)

        image.tofile(file)


def read_image(path):
    """Read image and output RGB image (0-1).

    Args:
        path (str): path to file

    Returns:
        array: RGB image (0-1)
    """
    img = cv2.imread(path)

    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) / 255.0

    return img


def resize_image(img):
    """Resize image and make it fit for network.

    Args:
        img (array): image

    Returns:
        tensor: data ready for network
    """
    height_orig = img.shape[0]
    width_orig = img.shape[1]

    if width_orig > height_orig:
        scale = width_orig / 384
    else:
        scale = height_orig / 384

    height = (np.ceil(height_orig / scale / 32) * 32).astype(int)
    width = (np.ceil(width_orig / scale / 32) * 32).astype(int)

    img_resized = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)

    img_resized = (
        torch.from_numpy(np.transpose(img_resized, (2, 0, 1))).contiguous().float()
    )
    img_resized = img_resized.unsqueeze(0)

    return img_resized


def resize_depth(depth, width, height):
    """Resize depth map and bring to CPU (numpy).

    Args:
        depth (tensor): depth
        width (int): image width
        height (int): image height

    Returns:
        array: processed depth
    """
    depth = torch.squeeze(depth[0, :, :, :]).to("cpu")

    depth_resized = cv2.resize(
        depth.numpy(), (width, height), interpolation=cv2.INTER_CUBIC
    )

    return depth_resized


def write_depth(path, depth, bits=1, absolute_depth=False, save_pfm=False,
                hue_depth=False, rgb_depth=False,
                fixed_depth_min: float = math.inf, fixed_depth_max: float = math.inf):
    """Write depth map to pfm and png file.

    Args:
        path (str): filepath without extension
        depth (array): depth
    """
    if save_pfm:
        write_pfm(path + ".pfm", depth.astype(np.float32))

    depth_min = math.inf
    depth_max = math.inf

    if absolute_depth:
        out = depth
    else:
        depth_min = fixed_depth_min if not math.isinf(fixed_depth_min) else depth.min()
        depth_max = fixed_depth_max if not math.isinf(fixed_depth_max) else depth.max()

        max_val = (2 ** (8 * bits)) - 1
        image_type = "uint16" if bits == 2 else "uint8"

        if depth_max - depth_min > np.finfo("float").eps:
            normalized_depth = (depth - depth_min) / (depth_max - depth_min)
            normalized_depth = np.clip(normalized_depth, 0, 1)

            if hue_depth:
                # opencv uses only 180.0 for hsv
                # https://stackoverflow.com/a/24974804/1138326
                out = (1.0 - normalized_depth) * 180.0

                # make real grayscale image
                out = out.reshape((*out.shape, 1))
                shape = out.shape[:2]
                sv_channels = np.ones((*shape, 2)) * max_val
                out = np.concatenate((out, sv_channels), axis=2)
                out = cv2.cvtColor(out.astype(image_type), cv2.COLOR_HSV2BGR)
            elif rgb_depth:
                # recalculate normalized depth with 16 bit resolution
                max_val = (2 ** (8 * 2)) - 1
                normalized_depth = (depth - depth_min) / (depth_max - depth_min)
                normalized_depth = np.clip(normalized_depth, 0, 1)

                # embed into rgb
                out = np.around(max_val * normalized_depth).astype(int)
                out = np.expand_dims(out, axis=2)

                r_channel = out * 0
                g_channel = (out >> 8) & 0xff
                b_channel = out & 0xff

                out = np.concatenate((b_channel, g_channel, r_channel), axis=2)
            else:
                out = max_val * normalized_depth
        else:
            out = np.zeros(depth.shape, dtype=depth.dtype)

    cv2.imwrite(path + ".png", out.astype(image_type), [cv2.IMWRITE_PNG_COMPRESSION, 0])
    return depth_min, depth_max


def write_segm_img(path, image, labels, palette="detail", alpha=0.5):
    """Write depth map to pfm and png file.

    Args:
        path (str): filepath without extension
        image (array): input image
        labels (array): labeling of the image
    """

    mask = get_mask_pallete(labels, "ade20k")

    img = Image.fromarray(np.uint8(255 * image)).convert("RGBA")
    seg = mask.convert("RGBA")

    out = Image.blend(img, seg, alpha)

    out.save(path + ".png")

    return


def get_images_in_path(path: str):
    return get_files_in_path(path, ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.gif', '*.tiff'])


def get_files_in_path(path: str, extensions: [str] = ["*.*"]):
    return sorted([f for ext in extensions for f in glob.glob(os.path.join(path, ext))])
