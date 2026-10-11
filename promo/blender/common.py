"""宣传片 Blender 场景共用的配色、材质、灯光和渲染设置。"""
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / "output/promo-video/capture"
RENDER = ROOT / "output/promo-video/render"
FPS = 30

# 品牌色，与 webpage/css/site.css 一致
PAPER = (0.913, 0.930, 0.913)   # #f5f7f4 线性近似
MIST = (0.846, 0.913, 0.930)    # #edf5f7
INK = (0.0071, 0.0161, 0.0242)  # #14212b
GOLD = (0.658, 0.402, 0.074)    # #d4aa4e

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def mat(name, color, rough=0.4, metal=0.0, emission=None, strength=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = strength
    return m
def rounded(obj, radius, segments=10):
    mod = obj.modifiers.new("round", "BEVEL")
    mod.affect = "VERTICES" if obj.dimensions.z < 1e-4 else "EDGES"
    mod.width = radius
    mod.segments = segments
    mod.limit_method = "ANGLE"
    return mod


def build_world_and_lights():
    world = bpy.data.worlds.new("world")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*MIST, 1)
    bg.inputs["Strength"].default_value = 1.0

    def area(name, loc, energy, size, color=(1, 1, 1)):
        bpy.ops.object.light_add(type="AREA", location=loc)
        light = bpy.context.object
        light.name = name
        light.data.energy = energy
        light.data.size = size
        light.data.color = color
        direction = Vector((0, 0, 0)) - light.location
        light.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    area("key", (-2.2, -2.6, 2.4), 260, 2.5)
    area("fill", (2.6, -2.2, 0.4), 90, 3.0, MIST)
    area("rim", (1.2, 2.2, 2.0), 220, 1.5, (1.0, 0.82, 0.55))


def ease(fcurves_owner):
    if not fcurves_owner.animation_data or not fcurves_owner.animation_data.action:
        return
    action = fcurves_owner.animation_data.action
    curves = action.fcurves if hasattr(action, "fcurves") else [c for layer in action.layers for strip in layer.strips for bag in strip.channelbags for c in bag.fcurves]
    for curve in curves:
        for key in curve.keyframe_points:
            key.interpolation = "BEZIER"
            key.easing = "EASE_IN_OUT"


def build_camera(move, frames, target):
    bpy.ops.object.camera_add(location=move["cam"][0])
    cam = bpy.context.object
    cam.data.lens = 55
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = target
    cam.data.dof.aperture_fstop = 2.8
    track = cam.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    bpy.context.scene.camera = cam
    for frame, loc in ((1, move["cam"][0]), (frames, move["cam"][1])):
        cam.location = loc
        cam.keyframe_insert("location", frame=frame)
    ease(cam)
    return cam


def animate_rig(rig, move, frames):
    for frame, rot in ((1, move["rot"][0]), (frames, move["rot"][1])):
        rig.rotation_euler = [math.radians(a) for a in rot]
        rig.keyframe_insert("rotation_euler", frame=frame)
    ease(rig)


def setup_render(scene, clip, frames, preview):
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 16 if preview else 64
    scene.eevee.use_raytracing = not preview
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920
    scene.render.resolution_percentage = 50 if preview else 100
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = frames
    # AgX 高光过渡更柔和；屏幕录屏走自发光，不受影响太多
    views = [v.identifier for v in scene.view_settings.bl_rna.properties["view_transform"].enum_items]
    scene.view_settings.view_transform = "AgX" if "AgX" in views else "Standard"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    out = RENDER / (clip + ("_preview" if preview else ""))
    out.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(out / "f_")
