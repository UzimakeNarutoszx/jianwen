"""Blender background export helper. Run with Blender's bundled Python:
blender -b ajin.blend --python export-assets.py
"""
import bpy
from pathlib import Path

OUT = Path(__file__).resolve().parent
scene = bpy.context.scene
scene.render.film_transparent = True
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(OUT / 'ajin-hero.png')
bpy.ops.render.render(write_still=True)
