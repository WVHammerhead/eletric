"""Importa Hammerhead_topo.svg (3 camadas) no .blend. Uso:
blender -b Hammerhead.blend --python importar_topo.py -- saida.blend
"""
import bpy, sys, os
out = sys.argv[sys.argv.index("--")+1] if "--" in sys.argv else None
here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
svg = os.path.join(os.getcwd(), "Hammerhead_topo.svg")
before = set(bpy.data.objects)
bpy.ops.wm.grease_pencil_import_svg(filepath=svg, scale=3.7795) if hasattr(bpy.ops.wm, "grease_pencil_import_svg") else bpy.ops.import_curve.svg(filepath=svg)
new = [o for o in bpy.data.objects if o not in before]
col = bpy.data.collections.get("Topo_SVG") or bpy.data.collections.new("Topo_SVG")
if col.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(col)
for o in new:
    for c in o.users_collection: c.objects.unlink(o)
    col.objects.link(o)
    if o.type == 'GREASEPENCIL':
        o.rotation_euler[0] = -1.5707963267948966  # planta: y do SVG vira -Y
        o.name = 'Hammerhead_topo'
    print("NEW", o.name, o.type)
    if o.type == 'GREASEPENCIL':
        for l in o.data.layers: print("  LAYER", l.name)
if out: bpy.ops.wm.save_as_mainfile(filepath=out, copy=True)
