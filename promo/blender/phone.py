"""见闻宣传片：3D 手机样机镜头。

用法（在项目根目录）:
  blender -b --factory-startup --python promo/blender/phone.py -- <镜头名> <时长秒> [--preview]

屏幕贴图读取 output/promo-video/capture/<镜头名>.mp4，从 marks.json 的 cut_in 开始播放。
输出 PNG 序列到 output/promo-video/render/<镜头名>/，之后由 build.sh 合成。
"""
import json
import sys
import math
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (CAPTURE, FPS, GOLD, INK, ROOT, animate_rig, build_camera,  # noqa: E402
                    build_world_and_lights, mat, reset_scene, rounded, setup_render)

# 每个镜头的相机运动：起止位置、目标点、手机起止旋转（度）
MOVES = {
    "today":    dict(cam=((0.0, -3.6, 0.35), (0.0, -3.1, 0.15)), rot=((0, 0, -14), (0, 0, -4))),
    "article":  dict(cam=((0.35, -3.2, 0.55), (0.0, -2.6, 0.25)), rot=((0, 0, 8), (0, 0, 2))),
    "ask":      dict(cam=((-0.3, -3.3, -0.3), (0.0, -2.9, 0.0)), rot=((0, 0, -6), (0, 0, 6))),
    "discover": dict(cam=((0.0, -3.0, 0.2), (0.0, -3.4, 0.1)), rot=((0, 0, 10), (0, 0, -8))),
    "hook":     dict(cam=((0.0, -6.5, 1.4), (0.0, -3.4, 0.2)), rot=((-20, 0, -40), (0, 0, -6))),
}


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) < 2:
        raise SystemExit("用法: -- <镜头名> <时长秒> [--preview]")
    return argv[0], float(argv[1]), "--preview" in argv


def screen_material(clip, cut_in):
    """录屏视频做自发光贴图，从 cut_in 秒开始播放"""
    img = bpy.data.images.load(str(CAPTURE / f"{clip}.mp4"))
    m = bpy.data.materials.new("screen")
    m.use_nodes = True
    nodes, links = m.node_tree.nodes, m.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emit = nodes.new("ShaderNodeEmission")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Cubic"
    tex.image_user.frame_duration = img.frame_duration
    tex.image_user.frame_start = 1
    tex.image_user.frame_offset = int(round(cut_in * FPS))
    tex.image_user.use_auto_refresh = True
    links.new(tex.outputs["Color"], emit.inputs["Color"])
    links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return m


def build_phone(clip, cut_in):
    # 机身：0.78 × 1.62 × 0.08，屏幕比例与录屏 780×1688 一致
    bpy.ops.mesh.primitive_cube_add(size=1)
    body = bpy.context.object
    body.name = "body"
    body.scale = (0.78, 0.08, 1.62)
    bpy.ops.object.transform_apply(scale=True)
    rounded(body, 0.09, 12)
    bpy.ops.object.shade_smooth()
    body.data.materials.append(mat("body", INK, rough=0.32, metal=0.6))

    bpy.ops.mesh.primitive_plane_add(size=1, rotation=(math.pi / 2, 0, 0))
    screen = bpy.context.object
    screen.name = "screen"
    screen.scale = (0.72, 1.558, 1)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    screen.location = (0, -0.0405, 0)
    rounded(screen, 0.07, 10)

    screen.data.materials.append(screen_material(clip, cut_in))

    # 底部金色细线，呼应品牌色
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.0, -0.79))
    accent = bpy.context.object
    accent.scale = (0.18, 0.082, 0.006)
    accent.data.materials.append(mat("accent", GOLD, rough=0.3, metal=1.0))

    bpy.ops.object.empty_add(location=(0, 0, 0))
    rig = bpy.context.object
    rig.name = "rig"
    for o in (body, screen, accent):
        o.parent = rig
    return rig



def main():
    clip, seconds, preview = args()
    marks = json.loads((CAPTURE / "marks.json").read_text())
    source = "today" if clip == "hook" else clip
    cut_in = marks[source]["cut_in"]
    frames = int(round(seconds * FPS))
    scene = reset_scene()
    rig = build_phone(source, cut_in)
    build_world_and_lights()
    move = MOVES[clip]
    build_camera(move, frames, rig)
    animate_rig(rig, move, frames)
    setup_render(scene, clip, frames, preview)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f"output/promo-video/render/{clip}.blend"))
    bpy.ops.render.render(animation=True)
    print(f"RENDERED {clip} {frames} frames -> {scene.render.filepath}")


if __name__ == "__main__":
    main()
