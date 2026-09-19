"""Rebuild the original 10-second product film from local artwork.
Run: python webpage/assets/motion/generate_motion.py
Requires Pillow, numpy, imageio-ffmpeg. No network assets or credentials.
"""
from pathlib import Path
import math
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

OUT = Path(__file__).resolve().parent
ASSETS = OUT.parent
W, H, FPS, SECONDS = 960, 540, 24, 10
font_path = Path('C:/Windows/Fonts/msyh.ttc')
font_bold = Path('C:/Windows/Fonts/msyhbd.ttc')
font = lambda size, bold=False: ImageFont.truetype(str(font_bold if bold else font_path), size)
host = Image.open(ASSETS / '阿烬主机.png').convert('RGBA')
host = host.crop(host.getbbox())
character = Image.open(ASSETS / '阿烬.png').convert('RGB')
yy, xx = np.mgrid[0:H, 0:W]
glow = np.exp(-((xx - 640)**2 / 170000 + (yy - 220)**2 / 170000))
base = np.zeros((H, W, 3), dtype=np.uint8)
for i, color in enumerate((241, 239, 222)):
    base[:, :, i] = np.clip(color - 9 * (yy / H) + glow * 5, 0, 255)
base = Image.fromarray(base).convert('RGBA')
draw = ImageDraw.Draw(base)
draw.line((48, 53, 912, 53), fill='#bfccb9', width=1)
draw.text((48, 24), 'AJIN  /  A LITTLE COMPANION', font=font(12), fill='#3e5a49')
draw.text((817, 24), '见闻 · 原创', font=font(12), fill='#3e5a49')
draw.text((48, 106), '把陪伴，', font=font(47, True), fill='#243f32')
draw.text((48, 169), '放在身边。', font=font(47, True), fill='#243f32')
draw.text((52, 252), '一个有温度的小小伙伴。', font=font(16), fill='#5e7061')
draw.text((52, 282), '阿烬 · 从想象走进日常', font=font(13), fill='#6c7969')
draw.line((48, 488, 912, 488), fill='#bfccb9', width=1)
draw.text((48, 506), 'MADE WITH CURIOSITY', font=font(10), fill='#667761')
draw.text((770, 506), 'AJIN STUDIO  /  01', font=font(10), fill='#667761')

def frame(index):
    angle = 2 * math.pi * index / (FPS * SECONDS)
    image = base.copy()
    d = ImageDraw.Draw(image)
    # Architectural shapes and slow light movement return exactly to their origin.
    cx, cy = 706 + 8 * math.sin(angle), 268
    d.ellipse((cx-195, cy-190, cx+195, cy+190), fill='#d6deca')
    d.ellipse((cx-164, cy-157, cx+164, cy+157), outline='#c5d0b9', width=1)
    d.arc((cx-214, cy-207, cx+214, cy+207), 215, 327, fill='#6e8b70', width=1)
    shadow = Image.new('RGBA', (W,H))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((562, 394, 858, 438), fill=(36, 63, 50, 37))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(16)))
    size = 310 + round(8 * math.sin(angle))
    product = host.resize((size, round(size * host.height / host.width)), Image.Resampling.LANCZOS)
    image.alpha_composite(product, (round(550 + 5*math.sin(angle)), round(112 + 10*math.cos(angle))))
    # Original character appears as a small studio portrait, preserving the source.
    portrait = character.resize((101,89), Image.Resampling.LANCZOS).convert('RGBA')
    mask = Image.new('L', portrait.size); ImageDraw.Draw(mask).rounded_rectangle((0,0,100,88), radius=10, fill=255)
    portrait.putalpha(mask)
    image.alpha_composite(portrait, (51,345))
    d = ImageDraw.Draw(image)
    d.text((166, 358), '认识阿烬', font=font(15, True), fill='#314e3b')
    d.text((166, 386), '让每一天，多一点好奇。', font=font(12), fill='#65745f')
    for n in range(11):
        px = 480 + (n*73)%420 + 5*math.sin(angle+n)
        py = 89 + (n*41)%341 + 8*math.cos(angle+n*.8)
        radius = 1.0 + .6*(1+math.sin(angle+n))
        d.ellipse((px-radius,py-radius,px+radius,py+radius), fill='#faf8e9')
    return image.convert('RGB')

frame(0).save(OUT / 'ajin-studio-poster.jpg', quality=91, optimize=True)
command = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo', '-s', f'{W}x{H}', '-pix_fmt', 'rgb24', '-r', str(FPS), '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(OUT / 'ajin-studio.mp4')]
process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
for i in range(FPS * SECONDS):
    process.stdin.write(frame(i).tobytes())
process.stdin.close()
stderr = process.stderr.read()
if process.wait(): raise RuntimeError(stderr.decode(errors='replace'))
print(f'Created {OUT / "ajin-studio.mp4"}: {(OUT / "ajin-studio.mp4").stat().st_size:,} bytes')

# An unlettered companion loop for HTML foreground text and original character art.
def ambient(index):
    angle = 2 * math.pi * index / (FPS * SECONDS)
    light = np.exp(-((xx - (660 + 95*math.sin(angle)))**2 / 100000 + (yy - (180 + 50*math.cos(angle)))**2 / 65000))
    second = np.exp(-((xx - 180)**2 / 120000 + (yy - 450)**2 / 70000))
    pixels = np.empty((H,W,3), dtype=np.uint8)
    for channel,(base_value,lum) in enumerate(((23,32),(53,41),(41,29))):
        pixels[:,:,channel] = np.clip(base_value + lum*light + second*7,0,255)
    image = Image.fromarray(pixels)
    d = ImageDraw.Draw(image)
    for n in range(4):
        cx = 700 + 18*math.sin(angle+n*.4)
        cy = 230 + 10*math.cos(angle+n*.4)
        radius = 160 + n*52
        d.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),outline=(64+n*3,89+n*3,68+n*3),width=1)
    for n in range(18):
        px = (n*137+50)%W + 7*math.sin(angle+n)
        py = (n*71+25)%H + 6*math.cos(angle+n)
        d.ellipse((px,py,px+2,py+2),fill='#788f69')
    return image

ambient(0).save(OUT/'ajin-ambient-poster.jpg',quality=91,optimize=True)
ambient_command = command[:-1] + [str(OUT/'ajin-ambient.mp4')]
process = subprocess.Popen(ambient_command,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
for i in range(FPS*SECONDS): process.stdin.write(ambient(i).tobytes())
process.stdin.close(); stderr = process.stderr.read()
if process.wait(): raise RuntimeError(stderr.decode(errors='replace'))
print(f'Created ambient film: {(OUT / "ajin-ambient.mp4").stat().st_size:,} bytes')
