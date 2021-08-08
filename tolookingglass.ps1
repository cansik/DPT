param (
    [Parameter(Mandatory=$true)]
    [string]$video,
    [int]$fps = 30,
    [int]$crf = 25
)

Write-Host "converting $video into a looking glass video..."

$video_name = [io.path]::GetFileNameWithoutExtension($video)
$input = "input"
$output = "output_monodepth"

# cleanup dirs
Remove-Item "$input\*.*"
Remove-Item "$output\*.*"

# extract video
ffmpeg -i $video -r $fps/1 "$input/frame_%04d.jpg"

# run convertion
python run_monodepth.py

# create videos
ffmpeg -r $fps -i "$input/frame_%04d.jpg" -vcodec libx264 -crf $crf -pix_fmt yuv420p "$output/$video_name-color.mp4"
ffmpeg -r $fps -i "$output/frame_%04d.png" -vcodec libx264 -crf $crf -pix_fmt yuv420p "$output/$video_name-depth.mp4"

ffmpeg -i "$output/$video_name-color.mp4" -i "$output/$video_name-depth.mp4" -filter_complex hstack "lg-$video_name.mp4"

# convert to webm
# ffmpeg -i "lg-$video_name.mp4" -c:v libvpx-vp9 -crf $crf -b:v 0 -b:a 128k -c:a libopus "lg-$video_name.webm"

Write-Host "done!"