param (
    [Parameter(Mandatory=$true)]
    [string]$video,
    [int]$crf = 25,
    [switch]$static
)

Write-Host "converting $video into a RGB-D video..."

$video_name = [io.path]::GetFileNameWithoutExtension($video)
$input = "input"
$output = "output_monodepth"
$audio_file = "audio.wav"

# cleanup dirs
Remove-Item "$input\*.png"
Remove-Item "$output\*.png"

# extract fps
$fps = ffprobe -v error -select_streams v -of default=noprint_wrappers=1:nokey=1 -show_entries stream=r_frame_rate $video

# extract video
ffmpeg -i $video -r $fps/1 "$input/frame_%04d.png"

# extract audio
ffmpeg -i $video $audio_file

# run convertion
python run_monodepth.py --rgb-depth --bit-depth 1

# create videos
ffmpeg -r $fps -i "$input/frame_%04d.png" -vcodec libx264 -crf $crf -pix_fmt yuv420p "$output/$video_name-color.mp4"
ffmpeg -r $fps -i "$output/frame_%04d.png" -vcodec libx264 -crf $crf -pix_fmt yuv420p "$output/$video_name-depth.mp4"

ffmpeg -i "$output/$video_name-depth.mp4" -i "$output/$video_name-color.mp4" -filter_complex hstack "silent-$video_name.mp4"
ffmpeg -i "silent-$video_name.mp4" -i $audio_file -map 0:v -map 1:a -c:v copy -shortest "rgbd-$video_name.mp4"

Write-Host "removing temp files..."
rm "silent-$video_name.mp4"
rm $audio_file

Write-Host "done!"