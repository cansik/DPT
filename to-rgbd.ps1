param (
    [Parameter(Mandatory=$true)]
    [string]$video,
    [int]$crf = 25,
    [switch]$fixed
)

Write-Host "converting $video into a RGB-D video..."

if ( $fixed )
{
    Write-Output "Fixed depth enabled!"
    $fixed_depth_param = "--fixed-depth"
}

$video_name = [io.path]::GetFileNameWithoutExtension($video)
$input = "input"
$output = "output_monodepth"
$audio_file = "audio.wav"

# cleanup dirs
Remove-Item "$input\*.png"
Remove-Item "$output\*.png"

# extract fps
$fps = ffprobe -v error -select_streams v -of default=noprint_wrappers=1:nokey=1 -show_entries stream=r_frame_rate $video
Write-Host "video FPS: $fps"

# extract video
Write-Host "extracting frames..."
ffmpeg -y -hide_banner -loglevel error -i $video -r $fps/1 "$input/frame_%04d.png"

# extract audio
Write-Host "extracting audio..."
ffmpeg -y -hide_banner -loglevel error -i $video $audio_file

if($?)
{
    Write-Host "no audio detected!"
    $has_audio = $true
}

# run convertion
Write-Host "converting..."
python run_monodepth.py --rgb-depth --bit-depth 1 $fixed_depth_param

# create videos
Write-Host "create color video..."
ffmpeg -y -hide_banner -loglevel error -r $fps -i "$input/frame_%04d.png" -vcodec libx264 -crf $crf -pix_fmt yuv420p "$output/$video_name-color.mp4"
Write-Host "create depth video..."
ffmpeg -y -hide_banner -loglevel error -r $fps -i "$output/frame_%04d.png" -vcodec libx264 -crf $crf -pix_fmt yuv420p "$output/$video_name-depth.mp4"

Write-Host "hstack videos..."
ffmpeg -y -hide_banner -loglevel error -i "$output/$video_name-depth.mp4" -i "$output/$video_name-color.mp4" -filter_complex hstack "silent-$video_name.mp4"

if($has_audio)
{
    Write-Host "add audio to video..."
    ffmpeg -y -hide_banner -loglevel error -i "silent-$video_name.mp4" -i $audio_file -map 0:v -map 1:a -c:v copy -shortest "rgbd-$video_name.mp4"
}
else
{
   Write-Host "video has no audio..."
   Copy-Item -Path "silent-$video_name.mp4" -Destination "rgbd-$video_name.mp4"
}

Write-Host "removing temp files..."
rm "silent-$video_name.mp4"
rm $audio_file

Write-Host "done!"
exit