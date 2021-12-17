"""Compute segmentation maps for images in the input folder.
"""
import os
import glob
import cv2
import argparse

import numpy as np
import torch
import torch.nn.functional as F
import tqdm

import util.io
from util.io import get_images_in_path

from torchvision.transforms import Compose
from dpt.models import DPTSegmentationModel
from dpt.transforms import Resize, NormalizeImage, PrepareForNet


def run(input_path, output_path, model_path, model_type="dpt_hybrid", optimize=True):
    """Run segmentation network

    Args:
        input_path (str): path to input folder
        output_path (str): path to output folder
        model_path (str): path to saved model
    """
    print("initialize")

    # select device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("device: %s" % device)

    net_w = net_h = 480

    # load network
    if model_type == "dpt_large":
        model = DPTSegmentationModel(
            150,
            path=model_path,
            backbone="vitl16_384",
        )
    elif model_type == "dpt_hybrid":
        model = DPTSegmentationModel(
            150,
            path=model_path,
            backbone="vitb_rn50_384",
        )
    else:
        assert (
            False
        ), f"model_type '{model_type}' not implemented, use: --model_type [dpt_large|dpt_hybrid]"

    transform = Compose(
        [
            Resize(
                net_w,
                net_h,
                resize_target=None,
                keep_aspect_ratio=True,
                ensure_multiple_of=32,
                resize_method="minimal",
                image_interpolation_method=cv2.INTER_CUBIC,
            ),
            NormalizeImage(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
            PrepareForNet(),
        ]
    )

    model.eval()

    if optimize == True and device == torch.device("cuda"):
        model = model.to(memory_format=torch.channels_last)
        model = model.half()

    model.to(device)

    # get input
    img_names = get_images_in_path(input_path)
    num_images = len(img_names)

    # create output folder
    os.makedirs(output_path, exist_ok=True)

    print("start processing")

    with tqdm.tqdm(total=len(img_names)) as prog:
        for ind, img_name in enumerate(img_names):

            # print("  processing {} ({}/{})".format(img_name, ind + 1, num_images))

            # input
            img = util.io.read_image(img_name)
            img_input = transform({"image": img})["image"]

            # compute
            with torch.no_grad():
                sample = torch.from_numpy(img_input).to(device).unsqueeze(0)
                if optimize == True and device == torch.device("cuda"):
                    sample = sample.to(memory_format=torch.channels_last)
                    sample = sample.half()

                out = model.forward(sample)

                prediction = torch.nn.functional.interpolate(
                    out, size=img.shape[:2], mode="bicubic", align_corners=False
                )
                prediction = torch.argmax(prediction, dim=1) + 1
                prediction = prediction.squeeze().cpu().numpy()

            # output
            filename = os.path.join(
                output_path, os.path.splitext(os.path.basename(img_name))[0]
            )

            if args.mask is not None:
                filtered_predictions = prediction == args.mask

                # apply mask in opencv
                cv_mask = (filtered_predictions * 255).astype(np.uint8)

                # blur mask as a preprocess step
                if args.blur > 0:
                    cv2.blur(cv_mask, (args.blur, args.blur), dst=cv_mask)
                    cv2.threshold(cv_mask, 1, 255, cv2.THRESH_BINARY, dst=cv_mask)

                cv_image = cv2.imread(img_name)

                output_image = cv2.bitwise_and(cv_image, cv_image, mask=cv_mask)
                output_image[cv_mask == 0] = args.mask_background

                if args.threshold:
                    gray = cv2.cvtColor(output_image, cv2.COLOR_RGB2GRAY)
                    _, output_image = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY)

                cv2.imwrite("%s.png" % filename, output_image)
                # cv2.imwrite("%s.png" % filename, cv_mask)
            else:
                util.io.write_segm_img(filename, img, prediction, alpha=0.5)

            prog.update()

    print("finished")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-i", "--input_path", default="input", help="folder with input images"
    )

    parser.add_argument(
        "-o", "--output_path", default="output_semseg", help="folder for output images"
    )

    parser.add_argument(
        "-m",
        "--model_weights",
        default=None,
        help="path to the trained weights of model",
    )

    # 'vit_large', 'vit_hybrid'
    parser.add_argument("-t", "--model_type", default="dpt_hybrid", help="model type")

    parser.add_argument("--optimize", dest="optimize", action="store_true")
    parser.add_argument("--no-optimize", dest="optimize", action="store_false")
    parser.set_defaults(optimize=True)

    parser.add_argument("--mask", default=None, type=int, help="create masks of these ADE20K classes")
    parser.add_argument("--mask-background", default=[0, 0, 0], type=int, nargs=3,
                        metavar=("r", "g", "b"), help="Background color of the mask")
    parser.add_argument("--threshold", action="store_true", help="Threshold the image to create a black-white mask.")
    parser.add_argument("--blur", default=-1, type=int, help="mask blur factor to increase area")

    args = parser.parse_args()

    default_models = {
        "dpt_large": "weights/dpt_large-ade20k-b12dca68.pt",
        "dpt_hybrid": "weights/dpt_hybrid-ade20k-53898607.pt",
    }

    if args.model_weights is None:
        args.model_weights = default_models[args.model_type]

    # set torch options
    torch.backends.cudnn.enabled = True
    torch.backends.cudnn.benchmark = True

    # compute segmentation maps
    run(
        args.input_path,
        args.output_path,
        args.model_weights,
        args.model_type,
        args.optimize,
    )
