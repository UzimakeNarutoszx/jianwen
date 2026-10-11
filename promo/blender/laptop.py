"""见闻宣传片：横屏网站镜头，笔记本 + 前景手机，表达"手机读、电脑接着读"。

用法（在项目根目录）:
  blender -b --factory-startup --python promo/blender/laptop.py -- web <时长秒> [--preview]
"""
import json
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (CAPTURE, FPS, INK, ROOT, animate_rig, build_camera,  # noqa: E402
                    build_world_and_lights, mat, reset_scene, rounded, setup_render)
from phone import build_phone, screen_material  # noqa: E402

MOVE = dict(cam=((2.0, -5.6, 2.1), (0.5, -4.8, 1.3)), rot=((0, 0, 18), (0, 0, 8)))


def build_laptop(cut_in):
    # 屏幕 16:10，与 1440×900 录屏一致
    w, h = 2.4, 1.5
    bpy.ops.mesh.primitive_cube_add(size=1)
    lid = bpy.context.object
    lid.scale = (w + 0.08, 0.05, h + 0.08)
    bpy.ops.object.transform_apply(scale=True)
    rounded(lid, 0.04, 6)
    lid.data.materials.append(mat("lid", INK, rough=0.35, metal=0.7))

    bpy.ops.mesh.primitive_plane_add(size=1, rotation=(math.pi / 2, 0, 0))
    screen = bpy.context.object
    screen.scale = (w, h, 1)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    screen.location = (0, -0.026, 0)
    screen.data.materials.append(screen_material("web", cut_in))

    bpy.ops.mesh.primitive_cube_add(size=1)
    base = bpy.context.object
    base.scale = (w + 0.12, h * 0.9, 0.06)
    bpy.ops.object.transform_apply(scale=True)
    rounded(base, 0.04, 6)
    base.location = (0, -h * 0.45 + 0.02, -h / 2 - 0.03)
    base.data.materials.append(mat("base", INK, rough=0.35, metal=0.7))

    bpy.ops.object.empty_add(location=(0, 0, 0))
    rig = bpy.context.object
    rig.name = "laptop"
    for o in (lid, screen):
        o.parent = rig
    # 屏幕稍向后仰
    rig.rotation_euler = (math.radians(-8), 0, 0)
    base.parent = None
    return rig


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    seconds, preview = float(argv[1]), "--preview" in argv
    marks = json.loads((CAPTURE / "marks.json").read_text())
    frames = int(round(seconds * FPS))
    scene = reset_scene()
    laptop = build_laptop(marks["web"]["cut_in"])
    # 前景手机停在发现页的阅读器画面，与电脑上的阅读页呼应
    phone = build_phone("discover", marks["discover"]["cut_in"] + 9.0)
    phone.location = (1.55, -1.1, -0.35)
    phone.scale = (0.62, 0.62, 0.62)
    build_world_and_lights()
    bpy.ops.object.empty_add(location=(0.35, -0.4, 0.05))
    focus = bpy.context.object
    build_camera(MOVE, frames, focus)
    scene.camera.data.lens = 35
    scene.camera.data.dof.aperture_fstop = 4.0
    animate_rig(phone, MOVE, frames)
    setup_render(scene, "web", frames, preview)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "output/promo-video/render/web.blend"))
    bpy.ops.render.render(animation=True)
    print(f"RENDERED web {frames} frames")


main()
