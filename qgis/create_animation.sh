convert *.png -resize 768x402 resized_%03d.png
ffmpeg -framerate 10 -i resized_%03d.png -c:v libx264 -pix_fmt yuv420p path.mp4
# nebo
mogrify -resize 768x402 *.png
ffmpeg -framerate 10 -i %04d.png -c:v libx264 -pix_fmt yuv420p path.mp4


