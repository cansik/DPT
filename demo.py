import os
import shutil

import gradio as gr

from util.utils import call
from sys import platform

RESULT_DIR = "results"


def create_rgbd_video(input_video_path: str, fixed_depth: bool):
    project_name = os.path.splitext(os.path.basename(input_video_path))[0]
    result_file_name = f"rgbd-{project_name}.mp4"
    render_result_path = os.path.join(RESULT_DIR, result_file_name)

    print(f"starting conversion of {project_name}...")

    if platform == "win32":
        powershell_cmd = "powershell"
    else:
        powershell_cmd = "pwsh"

    command = f"{powershell_cmd} -File to-rgbd.ps1 {input_video_path}"

    if fixed_depth:
        command += " -fixed"

    print(f"Command: {command}")
    return_code = call(command)

    if return_code != 0:
        print("Could not process video!")
        return None

    # move result to results
    shutil.move(result_file_name, render_result_path)
    return render_result_path


def main():
    os.makedirs(RESULT_DIR, exist_ok=True)

    iface = gr.Interface(
        fn=create_rgbd_video,
        inputs=[
            gr.inputs.Video(type="mp4", optional=False, label="Input Video"),
            gr.inputs.Checkbox(default=False, label="Fixed Depth"),
        ],
        outputs=[
            gr.outputs.Video(type=None, label="RGB-D Video"),
        ],

        title="DPT RGB-D Video Converter",
        description="",
        theme="default",
        enable_queue=False,

        server_name="0.0.0.0",
        server_port=7880,

        allow_flagging=False
    )
    iface.launch(share=False, show_error=True)


if __name__ == "__main__":
    main()
