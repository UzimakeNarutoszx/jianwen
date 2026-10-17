"""Original 3D editorial identity. Runs only inside Blender; writes to this project."""
import math
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'public' / 'identity'
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 12
scene.cycles.use_denoising = True
scene.render.resolution_x = 960
scene.render.resolution_y = 540
scene.render.resolution_percentage = 100
scene.render.fps = 30
scene.frame_start, scene.frame_end = 1, 72
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(OUT / 'frame-')
scene.world = bpy.data.worlds.new('Paper studio')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0.88, 0.91, 0.87, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .7

def material(name, color, metal=0):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*color, 1)
    result.use_nodes = True
    bsdf = result.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Roughness'].default_value = .35
    return result

paper = material('Warm paper', (.88, .90, .85))
blue = material('Jianwen ink', (.025, .14, .20), .15)
gold = material('Chapter gold', (.65, .38, .09), .65)
bpy.ops.mesh.primitive_plane_add(size=200)
bpy.context.object.data.materials.append(paper)
for index, mat in enumerate([paper, blue, paper]):
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, .6 + index * .38), scale=(1.55, 1.05, .055))
    obj = bpy.context.object
    obj.name = ['Reading', 'Updates', 'Events'][index]
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new('Paper edge', 'BEVEL'); bevel.width = .06; bevel.segments = 4
    obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    for frame, angle in [(1, -.22 + index * .13), (72, .18 + index * .13)]:
        obj.rotation_euler.z = angle
        obj.location.z = .6 + index * .38 + (.09 if frame == 72 else 0)
        obj.keyframe_insert('rotation_euler', frame=frame)
        obj.keyframe_insert('location', frame=frame)
bpy.ops.mesh.primitive_torus_add(major_radius=.53, minor_radius=.035, location=(.1, .05, 2.15), rotation=(.5, .25, 0))
ring = bpy.context.object; ring.name = 'A week connected'; ring.data.materials.append(gold)
for frame, angle in [(1, 0), (72, math.pi * .6)]:
    ring.rotation_euler.z = angle; ring.keyframe_insert('rotation_euler', frame=frame)
for point, power, size in [((0, -3, 7), 900, 5), ((4, 3, 5), 700, 4)]:
    bpy.ops.object.light_add(type='AREA', location=point)
    light = bpy.context.object; light.data.energy = power; light.data.shape = 'DISK'; light.data.size = size
    light.rotation_euler = (Vector((0, 0, 1)) - light.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.object.camera_add(location=(4.6, -7.3, 5.8))
camera = bpy.context.object; camera.data.type = 'ORTHO'; camera.data.ortho_scale = 7.4
camera.rotation_euler = (Vector((0, 0, 1.1)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'identity.blend'))
bpy.ops.render.render(animation=True)
