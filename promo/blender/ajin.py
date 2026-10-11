"""见闻宣传片：阿烬硬件收尾镜头。

按 webpage/assets/blender/ajin/scene-spec.md：低面数硬件外壳、暖金色状态灯、深蓝底座、
55mm 镜头、三点柔光。镜头为 3/4 正面转台，状态灯逐渐亮起。

用法（在项目根目录）:
  blender -b --factory-startup --python promo/blender/ajin.py -- <时长秒> [--preview] [--still] [--dark]
  --dark 深色背景版本，输出到 render/ajin_dark/
  --still 额外按 README 约定导出 webpage/assets/blender/ajin/ajin-hero.png（透明背景）
"""
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (FPS, GOLD, INK, ROOT, build_world_and_lights, ease, mat,  # noqa: E402
                    reset_scene, rounded, setup_render)

NAVY = (0.0, 0.016, 0.051)       # #002040
SHELL = (0.016, 0.016, 0.016)    # #202020
TEAL = (0.527, 0.745, 0.745)     # #c0e0e0
ASSET_DIR = ROOT / "webpage/assets/blender/ajin"


def build_ajin():
    parts = []
    # 主体：低面数圆角外壳
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.62))
    shell = bpy.context.object
    shell.scale = (0.86, 0.62, 0.78)
    bpy.ops.object.transform_apply(scale=True)
    rounded(shell, 0.16, 3)  # 段数少，保留硬件的切面感
    shell.data.materials.append(mat("shell", SHELL, rough=0.45, metal=0.35))
    parts.append(shell)

    # 正面深色玻璃面板
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.312, 0.66))
    face = bpy.context.object
    face.scale = (0.66, 0.02, 0.5)
    bpy.ops.object.transform_apply(scale=True)
    rounded(face, 0.06, 4)
    face.data.materials.append(mat("glass", (0.004, 0.008, 0.014), rough=0.08, metal=0.0))
    parts.append(face)

    # 两只"眼睛"：暖金状态灯，强度做动画
    eye_mat = mat("eyes", (0.02, 0.015, 0.008), rough=0.3, emission=(1.0, 0.62, 0.22), strength=0.0)
    for x in (-0.15, 0.15):
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.055, depth=0.02,
                                            location=(x, -0.325, 0.7), rotation=(math.pi / 2, 0, 0))
        eye = bpy.context.object
        eye.data.materials.append(eye_mat)
        parts.append(eye)

    # 顶部细金线
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.2, 1.012))
    seam = bpy.context.object
    seam.scale = (0.5, 0.02, 0.008)
    seam.data.materials.append(mat("seam", GOLD, rough=0.25, metal=1.0))
    parts.append(seam)

    # 深蓝底座 + 发光环
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.62, depth=0.16, location=(0, 0, 0.08))
    base = bpy.context.object
    rounded(base, 0.03, 2)
    base.data.materials.append(mat("base", NAVY, rough=0.35, metal=0.5))
    parts.append(base)
    ring_mat = mat("ring", (0.02, 0.015, 0.008), rough=0.3, emission=(1.0, 0.62, 0.22), strength=0.0)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.6, minor_radius=0.012, major_segments=48,
                                     location=(0, 0, 0.165))
    ring = bpy.context.object
    ring.data.materials.append(ring_mat)
    parts.append(ring)

    bpy.ops.object.empty_add(location=(0, 0, 0))
    rig = bpy.context.object
    rig.name = "ajin"
    for p in parts:
        p.parent = rig
    return rig, (eye_mat, ring_mat)


def animate(rig, glow_mats, frames):
    # 3/4 正面转台：从 -40° 转到 -20°
    for frame, deg in ((1, -40), (frames, -20)):
        rig.rotation_euler = (0, 0, math.radians(deg))
        rig.keyframe_insert("rotation_euler", frame=frame)
    ease(rig)
    # 状态灯：前 0.6 秒熄灭，之后 1 秒内亮起
    on_start, on_end = int(0.6 * FPS), int(1.6 * FPS)
    for m in glow_mats:
        sock = m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
        for frame, value in ((1, 0.0), (on_start, 0.0), (on_end, 1.4), (frames, 1.1)):
            sock.default_value = value
            sock.keyframe_insert("default_value", frame=frame)


def build_camera(frames, target):
    bpy.ops.object.camera_add(location=(0.0, -4.6, 1.15))
    cam = bpy.context.object
    # 竖屏下 55mm 太紧，用 42mm 让主体占画面宽度约八成
    cam.data.lens = 42
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = target
    cam.data.dof.aperture_fstop = 2.8
    track = cam.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    bpy.context.scene.camera = cam
    # 缓慢推近
    for frame, y in ((1, -4.6), (frames, -4.0)):
        cam.location.y = y
        cam.keyframe_insert("location", frame=frame)
    ease(cam)
    return cam


def floor(dark=False):
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
    plane = bpy.context.object
    if dark:
        # 深色略反光地面，接住暖金灯的倒影
        plane.data.materials.append(mat("floor", (0.006, 0.012, 0.02), rough=0.25, metal=0.2))
    else:
        plane.data.materials.append(mat("floor", (0.846, 0.913, 0.930), rough=0.6))
        plane.is_shadow_catcher = True


def darken_world():
    bg = bpy.context.scene.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.004, 0.009, 0.014, 1)
    bg.inputs["Strength"].default_value = 1.0
    # 深色背景下主光收一点，轮廓光加强，突出外壳边缘
    bpy.data.objects["key"].data.energy = 160
    bpy.data.objects["fill"].data.energy = 30
    bpy.data.objects["rim"].data.energy = 420


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    seconds, preview, still, dark = float(argv[0]), "--preview" in argv, "--still" in argv, "--dark" in argv
    frames = int(round(seconds * FPS))
    scene = reset_scene()
    rig, glow = build_ajin()
    animate(rig, glow, frames)
    floor(dark)
    build_world_and_lights()
    if dark:
        darken_world()
    bpy.ops.object.empty_add(location=(0, 0, 0.55))
    build_camera(frames, bpy.context.object)
    clip = "ajin_dark" if dark else "ajin"
    setup_render(scene, clip, frames, preview)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f"output/promo-video/render/{clip}.blend"))
    bpy.ops.render.render(animation=True)
    print(f"RENDERED {clip} {frames} frames")

    if still:
        # 网站静态图：1600×1200 透明背景，取灯已亮的最后一帧
        scene.frame_set(frames)
        bpy.data.objects["Plane"].hide_render = True
        scene.render.film_transparent = True
        scene.render.resolution_x, scene.render.resolution_y = 1600, 1200
        scene.render.resolution_percentage = 100
        scene.render.image_settings.color_mode = "RGBA"
        scene.camera.data.lens = 70
        scene.render.filepath = str(ASSET_DIR / "ajin-hero.png")
        bpy.ops.render.render(write_still=True)
        print(f"STILL {scene.render.filepath}")


main()
